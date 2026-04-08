"""LLM service wrapper for Gemini and Grok (xAI) providers."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

try:
	import google.generativeai as genai
except Exception:  # pragma: no cover - optional dependency behavior
	genai = None


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
	text: str
	provider: str
	model: str
	raw: Optional[dict[str, Any]] = None


def _retry_sleep(attempt: int, base: float = 1.0, cap: float = 8.0) -> None:
	"""Simple exponential backoff."""
	seconds = min(cap, base * (2 ** max(attempt - 1, 0)))
	time.sleep(seconds)


def _get_env_value(name: str) -> Optional[str]:
	value = os.getenv(name, "").strip()
	return value or None


def _gemini_model_name() -> str:
	return os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip() or "gemini-3-flash-preview"


def _grok_model_name() -> str:
	return os.getenv("GROK_MODEL", "grok-4-fast-reasoning").strip() or "grok-4-fast-reasoning"


def _grok_base_url() -> str:
	return os.getenv("GROK_BASE_URL", "https://api.x.ai/v1").strip() or "https://api.x.ai/v1"


def _openrouter_model_name() -> str:
	return os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"


def _openrouter_base_url() -> str:
	return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip() or "https://openrouter.ai/api/v1"


def _print_gemini_token_usage(model: Any, prompt: str, response: Any, label: str) -> None:
	usage = getattr(response, "usage_metadata", None)
	prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
	output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
	total_tokens = getattr(usage, "total_token_count", None) if usage else None

	if any(value is not None for value in [prompt_tokens, output_tokens, total_tokens]):
		logger.info(
			"[TOKEN USAGE][%s] prompt=%s, output=%s, total=%s",
			label,
			prompt_tokens if prompt_tokens is not None else "n/a",
			output_tokens if output_tokens is not None else "n/a",
			total_tokens if total_tokens is not None else "n/a",
		)
		return

	if model is not None and hasattr(model, "count_tokens"):
		try:
			count_result = model.count_tokens(prompt)
			estimated_prompt_tokens = getattr(count_result, "total_tokens", None)
			if estimated_prompt_tokens is not None:
				logger.info("[TOKEN USAGE][%s] prompt~= %s", label, estimated_prompt_tokens)
				return
		except Exception:
			pass

	logger.info("[TOKEN USAGE][%s] unavailable", label)


class LLMClient:
	"""Unified LLM client for Gemini, Grok, and OpenRouter providers."""

	def __init__(self, provider: str) -> None:
		self.provider = provider.lower()
		if self.provider not in {"gemini", "grok", "openrouter"}:
			raise ValueError("Unsupported LLM provider: %s" % provider)

		self.gemini_model = None
		if self.provider == "gemini":
			self.gemini_model = self._create_gemini_model()

	def _create_gemini_model(self) -> Any:
		api_key = _get_env_value("GEMINI_API_KEY")
		if not api_key:
			logger.warning("GEMINI_API_KEY is missing")
			return None
		if genai is None:
			logger.error("google-generativeai is not available")
			return None

		genai.configure(api_key=api_key)
		return genai.GenerativeModel(_gemini_model_name())

	def ask(
		self,
		prompt: str,
		*,
		system_prompt: Optional[str] = None,
		max_retries: int = 2,
		temperature: Optional[float] = None,
	) -> Optional[LLMResponse]:
		"""Ask the configured LLM provider and return a normalized response."""
		if self.provider == "gemini":
			return self._ask_gemini(prompt, system_prompt=system_prompt, max_retries=max_retries)
		if self.provider == "grok":
			return self._ask_grok(
				prompt,
				system_prompt=system_prompt,
				max_retries=max_retries,
				temperature=temperature,
			)
		return self._ask_openrouter(
			prompt,
			system_prompt=system_prompt,
			max_retries=max_retries,
			temperature=temperature,
		)

	def _ask_gemini(
		self,
		prompt: str,
		*,
		system_prompt: Optional[str],
		max_retries: int,
	) -> Optional[LLMResponse]:
		if not self.gemini_model:
			logger.warning("Gemini model is not configured")
			return None

		full_prompt = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"
		for attempt in range(1, max_retries + 2):
			try:
				response = self.gemini_model.generate_content(full_prompt)
				text = (getattr(response, "text", "") or "").strip()
				_print_gemini_token_usage(self.gemini_model, full_prompt, response, "GEMINI")
				return LLMResponse(text=text, provider="gemini", model=_gemini_model_name())
			except Exception as error:
				logger.error("Gemini request failed (attempt %s): %s", attempt, error)
				if attempt <= max_retries:
					_retry_sleep(attempt)
					continue
				return None
		return None

	def _ask_grok(
		self,
		prompt: str,
		*,
		system_prompt: Optional[str],
		max_retries: int,
		temperature: Optional[float],
	) -> Optional[LLMResponse]:
		api_key = _get_env_value("GROK_API_KEY")
		if not api_key:
			logger.warning("GROK_API_KEY is missing")
			return None

		url = f"{_grok_base_url()}/chat/completions"
		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		}
		messages = []
		if system_prompt:
			messages.append({"role": "system", "content": system_prompt})
		messages.append({"role": "user", "content": prompt})

		payload: dict[str, Any] = {
			"model": _grok_model_name(),
			"messages": messages,
		}
		if temperature is not None:
			payload["temperature"] = temperature

		for attempt in range(1, max_retries + 2):
			try:
				response = requests.post(url, headers=headers, json=payload, timeout=60)
				if response.status_code != 200:
					raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
				data = response.json()
				choices = data.get("choices", [])
				message = choices[0].get("message", {}) if choices else {}
				text = (message.get("content", "") or "").strip()
				return LLMResponse(text=text, provider="grok", model=_grok_model_name(), raw=data)
			except Exception as error:
				logger.error("Grok request failed (attempt %s): %s", attempt, error)
				if attempt <= max_retries:
					_retry_sleep(attempt)
					continue
				return None
		return None

	def _ask_openrouter(
		self,
		prompt: str,
		*,
		system_prompt: Optional[str],
		max_retries: int,
		temperature: Optional[float],
	) -> Optional[LLMResponse]:
		api_key = _get_env_value("OPENROUTER_API_KEY")
		if not api_key:
			logger.warning("OPENROUTER_API_KEY is missing")
			return None

		url = f"{_openrouter_base_url()}/chat/completions"
		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		}
		messages = []
		if system_prompt:
			messages.append({"role": "system", "content": system_prompt})
		messages.append({"role": "user", "content": prompt})

		payload: dict[str, Any] = {
			"model": _openrouter_model_name(),
			"messages": messages,
		}
		if temperature is not None:
			payload["temperature"] = temperature

		for attempt in range(1, max_retries + 2):
			try:
				response = requests.post(url, headers=headers, json=payload, timeout=60)
				if response.status_code != 200:
					raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
				data = response.json()
				choices = data.get("choices", [])
				message = choices[0].get("message", {}) if choices else {}
				text = (message.get("content", "") or "").strip()
				return LLMResponse(text=text, provider="openrouter", model=_openrouter_model_name(), raw=data)
			except Exception as error:
				logger.error("OpenRouter request failed (attempt %s): %s", attempt, error)
				if attempt <= max_retries:
					_retry_sleep(attempt)
					continue
				return None
		return None


def create_llm_client(provider: str) -> LLMClient:
	"""Factory for LLMClient. Provider values: gemini, grok, or openrouter."""
	return LLMClient(provider)
