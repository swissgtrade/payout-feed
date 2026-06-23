from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent


@dataclass
class WordPressConfig:
    site_url: str
    post_type: str = "firmup_payout"
    post_status: str = "publish"
    meta_key_payout_id: str = "firmup_payout_id"
    title_template: str = "{first_name} — {amount}"

    @classmethod
    def from_dict(cls, data: dict) -> WordPressConfig:
        return cls(
            site_url=str(data.get("site_url", "https://swissfirmup.com")).rstrip("/"),
            post_type=str(data.get("post_type", "firmup_payout")),
            post_status=str(data.get("post_status", "publish")),
            meta_key_payout_id=str(data.get("meta_key_payout_id", "firmup_payout_id")),
            title_template=str(data.get("title_template", "{first_name} — {amount}")),
        )


@dataclass
class PublishResult:
    payout_id: str
    media_id: int | None
    post_id: int | None
    title: str
    filename: str
    dry_run: bool
    media_request: dict[str, Any]
    post_request: dict[str, Any]


class WordPressClient:
    def __init__(
        self,
        config: WordPressConfig,
        *,
        username: str | None = None,
        app_password: str | None = None,
        dry_run: bool = False,
        export_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.username = username
        self.app_password = app_password
        self.dry_run = dry_run
        self.export_dir = export_dir or ROOT / "simulation"
        self.session = requests.Session()
        if username and app_password:
            self.session.auth = (username, app_password)

    @property
    def rest_base(self) -> str:
        return f"{self.config.site_url}/wp-json/wp/v2"

    def build_title(self, payout: dict) -> str:
        from certificate import first_name_only, format_amount

        return self.config.title_template.format(
            first_name=first_name_only(payout.get("fullName")),
            amount=format_amount(payout),
            program=payout.get("programName") or "",
            payout_id=payout.get("id") or "",
        )

    def upload_media(self, image: Image.Image, filename: str, title: str) -> dict[str, Any]:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        request_info = {
            "method": "POST",
            "url": f"{self.rest_base}/media",
            "headers": {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "image/png",
            },
            "body_bytes": len(image_bytes),
            "title": title,
        }

        if self.dry_run:
            return {
                "id": None,
                "source_url": f"simulation/certificates/{filename}",
                "dry_run": True,
                "request": request_info,
            }

        response = self.session.post(
            f"{self.rest_base}/media",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "image/png",
            },
            data=image_bytes,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        payload["request"] = request_info
        return payload

    def create_payout_post(
        self,
        payout: dict,
        *,
        featured_media_id: int,
        title: str,
    ) -> dict[str, Any]:
        payout_id = str(payout["id"])
        request_body = {
            "title": title,
            "status": self.config.post_status,
            "featured_media": featured_media_id,
            "meta": {
                self.config.meta_key_payout_id: payout_id,
            },
        }
        request_info = {
            "method": "POST",
            "url": f"{self.rest_base}/{self.config.post_type}",
            "json": request_body,
        }

        if self.dry_run:
            return {
                "id": None,
                "dry_run": True,
                "request": request_info,
            }

        response = self.session.post(
            f"{self.rest_base}/{self.config.post_type}",
            json=request_body,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        payload["request"] = request_info
        return payload

    def publish_payout(self, payout: dict, image: Image.Image) -> PublishResult:
        payout_id = str(payout["id"])
        filename = f"payout-{payout_id}.png"
        title = self.build_title(payout)

        if self.dry_run:
            cert_dir = self.export_dir / "certificates"
            cert_dir.mkdir(parents=True, exist_ok=True)
            image.save(cert_dir / filename)

        media = self.upload_media(image, filename, title)
        media_id = media.get("id")
        if not self.dry_run and media_id is None:
            raise RuntimeError(f"Upload média sans ID pour {payout_id}")

        fake_media_id = media_id if media_id is not None else 1000 + hash(payout_id) % 9000
        post = self.create_payout_post(
            payout,
            featured_media_id=int(fake_media_id),
            title=title,
        )

        return PublishResult(
            payout_id=payout_id,
            media_id=media_id,
            post_id=post.get("id"),
            title=title,
            filename=filename,
            dry_run=self.dry_run,
            media_request=media.get("request", {}),
            post_request=post.get("request", {}),
        )

    def append_export(self, results: list[PublishResult]) -> Path:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        export_path = self.export_dir / "wordpress-export.json"
        payload = {
            "site_url": self.config.site_url,
            "post_type": self.config.post_type,
            "dry_run": self.dry_run,
            "items": [
                {
                    "payout_id": item.payout_id,
                    "title": item.title,
                    "filename": item.filename,
                    "media_id": item.media_id,
                    "post_id": item.post_id,
                    "media_request": item.media_request,
                    "post_request": item.post_request,
                }
                for item in results
            ],
        }
        export_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return export_path

    def check_connection(self) -> dict[str, Any]:
        if self.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "site_url": self.config.site_url,
                "message": "Mode simulation — aucun appel réseau vers WordPress.",
            }

        response = self.session.get(f"{self.config.site_url}/wp-json/", timeout=30)
        response.raise_for_status()
        root = response.json()
        routes = root.get("routes", {})
        post_route = routes.get(f"/wp/v2/{self.config.post_type}")
        return {
            "ok": True,
            "site_url": self.config.site_url,
            "site_name": root.get("name"),
            "post_type_registered": post_route is not None,
            "post_type": self.config.post_type,
        }
