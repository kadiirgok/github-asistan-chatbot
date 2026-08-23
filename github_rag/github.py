# -*- coding: utf-8 -*-
"""GitHub içerik alımı: kullanıcı adı / link -> repo listesi + README'ler.

GitHub REST API'si kullanılır (web scraping yok). Opsiyonel GITHUB_TOKEN ile
saatlik istek limiti 60'tan 5000'e çıkar; token yoksa da temel kullanım çalışır.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"


def resolve_target(target: str) -> dict:
    """Kullanıcı girdisini normalleştirir; {"kind", "owner", "repo"} döndürür.

    Kabul edilen biçimler:
      - "kadiirgok"                     -> kullanıcı
      - "https://github.com/kadiirgok"  -> kullanıcı
      - "github.com/kadiirgok/bilgi-tr" -> tek repo
      - "kadiirgok/bilgi-tr"            -> tek repo
    """
    t = (target or "").strip().strip("/")
    t = t.replace("https://", "").replace("http://", "")
    t = t.removeprefix("www.")
    t = t.removeprefix("github.com/").strip("/")

    parts = [p for p in t.split("/") if p]
    if len(parts) == 1:
        return {"kind": "user", "owner": parts[0], "repo": None}
    if len(parts) >= 2:
        return {"kind": "repo", "owner": parts[0], "repo": parts[1]}
    raise ValueError(f"Geçersiz GitHub hedefi: {target!r}")


def _headers(token: str) -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def list_repos(user: str, token: str = "") -> list[dict]:
    """Kullanıcının (fork hariç) repolarını döndürür: [{name, full_name, html_url}]."""
    repos = []
    page = 1
    while True:
        resp = requests.get(
            f"{GITHUB_API}/users/{user}/repos",
            headers=_headers(token),
            params={"per_page": 100, "page": page, "type": "owner", "sort": "updated"},
            timeout=30,
        )
        if resp.status_code == 404:
            raise ValueError(f"GitHub kullanıcısı bulunamadı: {user}")
        if resp.status_code == 403:
            raise RuntimeError(
                "GitHub API limiti aşıldı (403). .env dosyasına GITHUB_TOKEN ekleyerek "
                "limiti 60/saat yerine 5000/saat'e çıkarın."
            )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def fetch_readme(owner: str, repo: str, token: str = "") -> str | None:
    """Repo'nun README metnini döndürür; yoksa None."""
    resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/readme",
        headers={**_headers(token), "Accept": "application/vnd.github.raw"},
        timeout=30,
    )
    if resp.status_code in (404, 204):
        return None
    resp.raise_for_status()
    text = (resp.text or "").strip()
    return text or None


# Gerçek bilgi içermeyen, araçların otomatik ürettiği README'lerin belirteçleri.
_BOILERPLATE_ISARETLERI = (
    "a new flutter project",
    "lab: write your first flutter app",
    "getting started with create react app",
    "this project was bootstrapped with",
    "bootstrapped with create-react-app",
)


def _readme_bos_metin(text: str) -> bool:
    """README'nin şablon (boilerplate) olup olmadığını döndürür.

    Flutter/CRA gibi araçların ürettiği hazır README'ler proje hakkında hiçbir
    şey söylemez; bunlar indekse alınmazsa soru koda düşer ve asıl yapı okunur.
    """
    t = (text or "").lower()
    return any(i in t for i in _BOILERPLATE_ISARETLERI)


def _repo_metadata(r: dict) -> dict:
    """GitHub repo nesnesinden yalnızca sunum/özet için gereken alanları alır."""
    lic = r.get("license") or {}
    return {
        "name": r.get("name", ""),
        "full_name": r.get("full_name", ""),
        "description": (r.get("description") or "").strip(),
        "language": r.get("language") or "",
        "stars": r.get("stargazers_count", 0),
        "forks": r.get("forks_count", 0),
        "updated_at": r.get("updated_at", ""),
        "created_at": r.get("created_at", ""),
        "html_url": r.get("html_url", ""),
        "homepage": r.get("homepage") or "",
        "license": lic.get("spdx_id") or "",
    }


def fetch_repo_metadata(owner: str, repo: str, token: str = "") -> dict | None:
    """Tek reponun metadata'sını döndürür; bulunamazsa None."""
    resp = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}",
                        headers=_headers(token), timeout=30)
    if resp.status_code != 200:
        return None
    return _repo_metadata(resp.json())


def fetch_metadata(target: str, token: str = "") -> list[dict]:
    """Yalnızca repo metadata'sını döndürür (README/embedding yok; hafif).

    Cache'li koleksiyonda metadata yan dosyası eksikse, index() bunu tek istekle
    yeniden doldurmak için kullanır.
    """
    parsed = resolve_target(target)
    if parsed["kind"] == "repo":
        meta = fetch_repo_metadata(parsed["owner"], parsed["repo"], token)
        return [meta] if meta else []
    return [_repo_metadata(r) for r in list_repos(parsed["owner"], token)]


def ingest_github(target: str, token: str = "") -> tuple[list[dict], list[dict]]:
    """Hedefi çözümleyip (docs, metadata) döndürür.

    docs:     [{"text","source","url"}]                    -> embedding için
    metadata: [{name, description, language, stars, ...}]  -> sunum/özet için
    """
    parsed = resolve_target(target)
    docs = []
    metadata = []

    if parsed["kind"] == "repo":
        owner, repo = parsed["owner"], parsed["repo"]
        meta = fetch_repo_metadata(owner, repo, token)
        if meta:
            metadata.append(meta)
        text = fetch_readme(owner, repo, token)
        if text and not _readme_bos_metin(text):
            docs.append({"text": text, "source": repo,
                         "url": f"https://github.com/{owner}/{repo}"})
        return docs, metadata

    for r in list_repos(parsed["owner"], token):
        name = r.get("name", "")
        full = r.get("full_name", "")
        if not name:
            continue
        metadata.append(_repo_metadata(r))
        text = fetch_readme(parsed["owner"], name, token)
        if text and not _readme_bos_metin(text):
            docs.append({"text": text, "source": name,
                         "url": r.get("html_url", f"https://github.com/{full}")})
    return docs, metadata


# --- Kod dosyası çekme (Katman 2) ---

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs",
    ".dart", ".java", ".kt", ".kts", ".go", ".rs", ".cs", ".cpp", ".c", ".h", ".hpp",
    ".rb", ".php", ".swift", ".sh", ".vue", ".sql", ".html", ".css", ".scss",
    ".yaml", ".yml", ".toml", ".md",
}

# Devasa repolarda gereksiz dizinleri dışarıda bırak (build ürünleri, bağımlılıklar).
EXCLUDED_DIRS = {
    "node_modules", "dist", "build", ".git", "__pycache__", ".venv", "venv",
    "vendor", "target", ".idea", ".vscode", ".dart_tool", ".next", "coverage",
}

EXCLUDED_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                      "poetry.lock", "Cargo.lock", "go.sum"}


def _default_branch(owner: str, repo: str, token: str = "") -> str:
    resp = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}",
                        headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json().get("default_branch", "main")


def fetch_code_file(owner: str, repo: str, branch: str, path: str) -> str | None:
    """raw.githubusercontent.com üzerinden tek dosyayı çeker (API limitine takılmaz)."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        return None
    return resp.text


def ingest_code(owner: str, repo: str, token: str = "",
                max_files: int = 200, max_size: int = 1_500_000) -> list[dict]:
    """Repo'nun kaynak dosyalarını filtreleyip doküman listesi olarak döndürür.

    Dosyalar git tree ile listelenir, raw CDN üzerinden paralel çekilir.
    `source` alanı dosya yoludur (örn. "github_rag/retrieval.py").
    """
    branch = _default_branch(owner, repo, token)

    tree_resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
        headers=_headers(token), timeout=60,
    )
    tree_resp.raise_for_status()
    tree = tree_resp.json().get("tree", [])

    secilenler = []  # (path, size)
    total = 0
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        size = item.get("size", 0)
        if Path(path).suffix.lower() not in CODE_EXTENSIONS:
            continue
        parcalar = path.split("/")
        if any(p in EXCLUDED_DIRS for p in parcalar):
            continue
        if Path(path).name in EXCLUDED_FILENAMES:
            continue
        if size > 50_000:  # tek dosya üst sınırı
            continue
        if len(secilenler) >= max_files or total + size > max_size:
            break
        secilenler.append((path, size))
        total += size

    docs = []

    def _fetchet(p):
        path, _size = p
        text = fetch_code_file(owner, repo, branch, path)
        return path, text

    with ThreadPoolExecutor(max_workers=8) as ex:
        for path, text in ex.map(_fetchet, secilenler):
            if text and text.strip():
                # Şablon README'yi kod indeksine de alma (gerçek bilgi içermez).
                if Path(path).suffix.lower() == ".md" and _readme_bos_metin(text):
                    continue
                docs.append({"text": text, "source": path,
                             "url": f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"})
    return docs
