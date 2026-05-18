"""TikTok API utilities."""

import json
import mimetypes
import os
import time
from typing import Optional

import requests


DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024


def _build_chunk_size_candidates(video_size: int) -> list[int]:
    """Build conservative chunk-size candidates for TikTok Direct Post."""
    preferred_sizes = [5 * 1024 * 1024, 2 * 1024 * 1024, 1 * 1024 * 1024, DEFAULT_CHUNK_SIZE]
    candidates: list[int] = []

    for chunk_size in preferred_sizes:
        if video_size > 0:
            chunk_size = min(chunk_size, video_size)
        if chunk_size <= 0:
            continue
        if chunk_size not in candidates:
            candidates.append(chunk_size)

    if video_size > 0 and video_size not in candidates:
        candidates.append(video_size)

    return candidates or [DEFAULT_CHUNK_SIZE]


def _extract_tiktok_error(response: requests.Response) -> tuple[str, str]:
    """Extract TikTok error code/message from JSON response if present."""
    try:
        payload = response.json()
    except Exception:
        return "", ""

    error_obj = payload.get("error")
    if isinstance(error_obj, dict):
        return str(error_obj.get("code", "")), str(error_obj.get("message", ""))

    # Some endpoints may return OAuth-style errors.
    code = str(payload.get("error", ""))
    message = str(payload.get("error_description", payload.get("message", "")))
    return code, message


def _raise_for_tiktok_response(resp: requests.Response, context: str) -> None:
    """Raise meaningful exceptions based on TikTok error response."""
    if resp.ok:
        return

    code, message = _extract_tiktok_error(resp)
    if code in {"access_token_invalid", "invalid_access_token"}:
        raise Exception("Token expired")
    if code == "scope_not_authorized":
        raise Exception("Scope not authorized: video.publish")
    if code == "unaudited_client_can_only_post_to_private_accounts":
        raise Exception(
            "Unaudited app restriction: account must be private for direct publish "
            "or app must pass TikTok audit"
        )

    # Fallback classification for auth responses without structured code.
    if resp.status_code == 401:
        raise Exception("Token expired")

    raise RuntimeError(f"{context} failed: status={resp.status_code}, code={code}, message={message}")


def fetch_user_info(access_token: str) -> Optional[dict]:
    """Fetch user information from TikTok API."""
    url = "https://open.tiktokapis.com/v2/user/info/"
    fields = "open_id,union_id,display_name,avatar_large_url,avatar_url"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        resp = requests.get(
            f"{url}?fields={fields}",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("data"):
            return data["data"]
        else:
            print("API error:", data.get("error"))
            return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise Exception("Token expired")
        print(f"Error fetching user info: {e}")
        return None
    except Exception as e:
        print(f"Error fetching user info: {e}")
        return None


def fetch_all_videos(access_token: str) -> list[dict]:
    """Fetch all videos from TikTok account (paginated)."""
    url = "https://open.tiktokapis.com/v2/video/list/"
    fields = "id,title,create_time,cover_image_url,share_url,duration,view_count,like_count,comment_count"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    all_videos = []
    cursor = None

    while True:
        body = {"max_count": 20}
        if cursor:
            body["cursor"] = cursor

        try:
            resp = requests.post(
                f"{url}?fields={fields}",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

            # Check for token expiration error
            if data.get("error", {}).get("code") == "invalid_access_token":
                raise Exception("Token expired")

            if data.get("error", {}).get("code") != "ok":
                print("API error:", data["error"])
                break

            videos = data["data"].get("videos", [])
            all_videos.extend(videos)
            print(f"  Fetched {len(videos)} videos (total so far: {len(all_videos)})")

            if not data["data"].get("has_more"):
                break
            cursor = data["data"].get("cursor")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("Token expired")
            raise

    return all_videos


def upload_video_to_tiktok(
    video_file_path: str,
    description: str,
    access_token: str,
) -> Optional[str]:
    """Direct-post a local video file to TikTok and return publish_id."""
    if not os.path.exists(video_file_path):
        print(f"❌ Video file not found: {video_file_path}")
        return None

    try:
        creator_info = _query_creator_info(access_token)
        privacy_level = _pick_privacy_level(creator_info)

        video_size = os.path.getsize(video_file_path)
        last_error: Optional[Exception] = None

        for chunk_size in _build_chunk_size_candidates(video_size):
            total_chunk_count = max(1, (video_size + chunk_size - 1) // chunk_size)

            try:
                publish_id, upload_url = _init_direct_post(
                    access_token=access_token,
                    title=description,
                    privacy_level=privacy_level,
                    video_size=video_size,
                    chunk_size=chunk_size,
                    total_chunk_count=total_chunk_count,
                )

                _upload_file_to_tiktok(
                    upload_url=upload_url,
                    video_file_path=video_file_path,
                    chunk_size=chunk_size,
                )

                print(f"✅ Video uploaded and submitted. publish_id={publish_id}")
                return publish_id

            except Exception as error:
                last_error = error
                message = str(error)

                if "Token expired" in message:
                    raise Exception("Token expired")
                if "Scope not authorized" in message:
                    raise Exception("Scope not authorized: video.publish")
                if "Unaudited app restriction" in message:
                    raise

                if "invalid_params" in message or "chunk" in message.lower() or "publish_id or upload_url" in message:
                    print(f"⚠️ TikTok upload init failed with chunk_size={chunk_size}: {error}")
                    continue

                print(f"❌ Error uploading video: {error}")
                return None

        print(f"❌ Error uploading video: {last_error}")
        return None

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise Exception("Token expired")
        print(f"❌ Error uploading video: {e}")
        return None
    except Exception as e:
        if "access_token_invalid" in str(e):
            raise Exception("Token expired")
        if "Scope not authorized" in str(e):
            raise Exception("Scope not authorized: video.publish")
        print(f"❌ Error uploading video: {e}")
        return None


def _query_creator_info(access_token: str) -> dict:
    """Get creator options required by TikTok Direct Post."""
    url = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    resp = requests.post(url, headers=headers, json={})
    _raise_for_tiktok_response(resp, "creator_info/query")
    payload = resp.json()
    error = payload.get("error", {})
    if error.get("code") not in (None, "ok"):
        if error.get("code") == "scope_not_authorized":
            raise Exception("Scope not authorized: video.publish")
        raise RuntimeError(f"creator_info/query failed: {error}")
    return payload.get("data", {})


def _pick_privacy_level(creator_info: dict) -> str:
    """Choose a valid privacy level returned by creator info."""
    options = creator_info.get("privacy_level_options") or []
    if not options:
        return "SELF_ONLY"
    if "SELF_ONLY" in options:
        return "SELF_ONLY"
    return options[0]


def _init_direct_post(
    access_token: str,
    title: str,
    privacy_level: str,
    video_size: int,
    chunk_size: int,
    total_chunk_count: int,
) -> tuple[str, str]:
    """Initialize Direct Post and return (publish_id, upload_url)."""
    url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    body = {
        "post_info": {
            "title": (title or "")[:2200],
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "brand_content_toggle": False,
            "brand_organic_toggle": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    }

    resp = requests.post(url, headers=headers, json=body)
    _raise_for_tiktok_response(resp, "video/init")
    payload = resp.json()
    error = payload.get("error", {})
    if error.get("code") not in (None, "ok"):
        if error.get("code") == "scope_not_authorized":
            raise Exception("Scope not authorized: video.publish")
        raise RuntimeError(f"video/init failed: {error}")

    data = payload.get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not publish_id or not upload_url:
        raise RuntimeError(f"video/init missing publish_id or upload_url: {payload}")
    return publish_id, upload_url


def _upload_file_to_tiktok(upload_url: str, video_file_path: str, chunk_size: int) -> None:
    """Upload binary video data to TikTok upload_url with Content-Range."""
    total_size = os.path.getsize(video_file_path)
    content_type = mimetypes.guess_type(video_file_path)[0] or "video/mp4"

    with open(video_file_path, "rb") as file_obj:
        start = 0
        while start < total_size:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break

            end = start + len(chunk) - 1
            headers = {
                "Content-Type": content_type,
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{total_size}",
            }
            resp = requests.put(upload_url, headers=headers, data=chunk)
            if not resp.ok:
                raise RuntimeError(
                    f"upload chunk failed: status={resp.status_code}, body={resp.text[:300]}"
                )
            start = end + 1


def save_user_data(user_info: Optional[dict], videos: list[dict], output_file: str) -> None:
    """Save user info and videos to JSON file."""
    user_data = {
        "user": user_info or {},
        "videos": videos,
        "saved_at": time.time()
    }
    
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
        print(f"✅ User data saved to {output_file}")
    except Exception as e:
        print(f"Error saving user data: {e}")
