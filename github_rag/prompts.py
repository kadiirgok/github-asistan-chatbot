# -*- coding: utf-8 -*-
"""LLM prompt şablonları.

Tüm yollar (README / kod / web) aynı sistem mesajını paylaşır: modeli "yalnızca
verilen bağlama dayan, uydurma, kısa ve doğrudan cevap ver" davranışına sabitler.
Soru şablonları yalnızca bağlamı çerçeveler.
"""

# Ortak sistem mesajı: küçük modellerdeki "bilmiyorum ama cevaplıyorum" tarzı
# çelişkili girişleri ve uydurmaları azaltır.
SYSTEM_PROMPT = (
    "Sen Türkçe konuşan bir yazılım asistanısın. Kullanıcının sorusunu YALNIZCA "
    "sana verilen bağlama dayanarak yanıtlarsın. Bağlamda olmayan hiçbir bilgiyi "
    "uydurma. Sayıları ve teknik terimleri değiştirmeden aktar. Cevabı açık ve "
    "düzenli ver: önce 1-2 cümlelik bir özet yaz, ardından bilgiyi madde işaretleri "
    "veya gerektiğinde küçük bir tabloyla düzenle. Gereksiz giriş cümlesi yapma."
)

# Yerel RAG (README): bağlam + soru -> kısa, kaynağa sadık cevap.
PROMPT_TEMPLATE = (
    "Bağlam:\n{context}\n\n"
    "Soru: {soru}\n\n"
    "Yanıt:"
)

# Kod katmanı için: dosya/ayar listelemek yerine amacı ve mimariyi sentezle.
CODE_PROMPT_TEMPLATE = (
    "Aşağıda bir projenin kaynak kodundan alınmış parçalar var. Bu parçalara "
    "dayanarak projenin NE yaptığını, hangi sorunu çözdüğünü, ana bileşenlerini ve "
    "bunların birbiriyle nasıl ilişkili olduğunu anlat. Yalnızca dosya adı ve ayar "
    "listelemek yerine amacı ve mimariyi açıkla. Şablon/boilerplate içerikleri yoksay.\n\n"
    "Kod parçaları:\n{context}\n\n"
    "Soru: {soru}\n\n"
    "Yanıt:"
)

# Web arama sonuçları için: yalnızca kaynakta yazan bilgiyi kullan.
WEB_PROMPT_TEMPLATE = (
    "Aşağıdaki arama sonuçlarına dayanarak soruyu yanıtla.\n\n"
    "{context}\n\n"
    "Soru: {soru}\n\n"
    "Yanıt:"
)
