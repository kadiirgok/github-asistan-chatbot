# -*- coding: utf-8 -*-
"""Üç katmanlı doğrulama: sayısal tutarlılık, eksik değer, konu uyumu.

Amaç: modelin sayı uydurmasını, bir listeyi tek değere indirmesini ve soruyu
alakasız bir bağlama kaydırmasını yakalayıp "asla sessizce yanlış bilgi vermemek".
"""

import re

from .retrieval import _kompakt

# Sayısal değer yakalama (ondalık, yüzde, para birimleri dahil).
_SAYI_RE = re.compile(r"(?<![\w])([+-]?\d+(?:[.,]\d+)?)(?![\w])")

# İki sayının "çok yakın" sayılabilmesi için göreli tolerans (yuvarlama farkı).
_SAYI_TOLERANS = 0.02

# Birbirine "liste" sayılacak kadar yakın iki ondalıklı sayı arasındaki azami
# karakter mesafesi.
_LISTE_BOSLUK = 25


def _sayi_normalize(token: str) -> str:
    t = token.strip().replace(",", ".")
    try:
        return f"{float(t):g}"
    except ValueError:
        return t


def _sayi_degeri(token: str) -> float | None:
    try:
        return float(token.strip().replace(",", "."))
    except ValueError:
        return None


def _sayilar_yakin(a: float, b: float) -> bool:
    return abs(a - b) <= _SAYI_TOLERANS * max(abs(a), abs(b), 1.0)


def dogrula_sayisal_tutarlilik(cevap: str, kaynak_metin: str, soru: str = "") -> bool:
    """Cevapta kaynaktan gelmeyen (uydurma) sayı var mı diye kabaca denetler.

    Sorudan gelen sayılar (örn. "data-science-project-52" içindeki 52) sayılmaz.
    Yalnızca "cevapta sorudan gelmeyen sayı var ama kaynakta hiç sayı yok"
    durumu uydurma kabul edilir; kaynakta sayı varsa cevaptaki sayılar o alana
    aittir kabul edilir. Tek tek eşleştirme kod cevaplarında (port/IP/sürüm gibi
    meşru sayılar) fazla yanlış pozitif üretir.
    """
    cevap_sayilari = _SAYI_RE.findall(cevap)
    if not cevap_sayilari:
        return True

    soru_norm = {_sayi_normalize(s) for s in _SAYI_RE.findall(soru or "")}
    soru_degerler = [d for d in (_sayi_degeri(s) for s in _SAYI_RE.findall(soru or "")) if d is not None]

    def _soruda_var(s: str) -> bool:
        if _sayi_normalize(s) in soru_norm:
            return True
        deger = _sayi_degeri(s)
        return deger is not None and any(_sayilar_yakin(deger, d) for d in soru_degerler)

    yeni_sayilar = [s for s in cevap_sayilari if not _soruda_var(s)]
    if not yeni_sayilar:
        return True  # cevaptaki tüm sayılar sorudan geliyor

    # Sorudan gelmeyen sayı var: kaynakta hiç sayı yoksa uydurma kabul et.
    return bool(_SAYI_RE.findall(kaynak_metin))


def _liste_sayilari(kaynak_metin: str) -> list[str]:
    """Kaynaktaki ilk 'liste'nin sayılarını döndürür (yoksa boş liste)."""
    eslesmeler = list(_SAYI_RE.finditer(kaynak_metin))
    ondalik = [m for m in eslesmeler if "." in m.group(0) or "," in m.group(0)]
    if len(ondalik) < 3:
        return []

    for i in range(len(ondalik) - 2):
        grup = [ondalik[i]]
        for j in range(i + 1, len(ondalik)):
            bosluk = kaynak_metin[grup[-1].end(): ondalik[j].start()]
            if len(bosluk) <= _LISTE_BOSLUK:
                grup.append(ondalik[j])
            else:
                break
        if len(grup) >= 3:
            return [m.group(0) for m in grup]
    return []


def dogrula_eksik_deger(cevap: str, kaynak_metin: str) -> bool:
    """Kaynaktaki bir 'liste'nin cevapta eksik kalıp kalmadığını kontrol eder."""
    liste_sayilari = _liste_sayilari(kaynak_metin)
    if not liste_sayilari:
        return True

    cevap_norm = {_sayi_normalize(s) for s in _SAYI_RE.findall(cevap)}
    liste_norm = {_sayi_normalize(s) for s in liste_sayilari}
    return liste_norm <= cevap_norm


def dogrula_konu_uyumu(soru: str, source: str, bilinen_anahtarlar: list[str]) -> bool:
    """Soruda bilinen bir repo adı geçiyorsa, çekilen kaynağın o repo olmasını şart koşar.

    Repo adları dil bağımsızdır; README metninde repo adı geçmese bile kaynak
    (source) adından doğrulanır. Repo adı yoksa müdahale etmez — retrieval'in
    cosine eşiği zaten semantik alakayı garantiler; çapraz dilde (Türkçe soru ->
    İngilizce README) leksikal örtüşme yanıltıcı olur.
    """
    soru_kompakt = _kompakt(soru)
    source_kompakt = _kompakt(source or "")

    for anahtar in bilinen_anahtarlar:
        if len(anahtar) >= 4 and anahtar in soru_kompakt:
            return anahtar in source_kompakt

    return True
