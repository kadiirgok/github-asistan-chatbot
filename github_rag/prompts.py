# -*- coding: utf-8 -*-
"""LLM prompt şablonları.

Tüm yollar (README / kod / web) aynı sistem mesajını paylaşır: modeli "yalnızca
verilen bağlama dayan, uydurma, kısa ve doğrudan cevap ver" davranışına sabitler.
Soru şablonları yalnızca bağlamı çerçeveler.
"""

# Ortak sistem mesajı: küçük modellerdeki "bilmiyorum ama cevaplıyorum" tarzı
# çelişkili girişleri ve uydurmaları azaltır.
SYSTEM_PROMPT = (
    "Sen bir kullanıcının GitHub repoları hakkında soru yanıtlayan Türkçe bir yazılım "
    "asistanısın. Kurallar:\n"
    "1) YALNIZCA verilen bağlamı kullan; bağlamda olmayanı uydurma, tahmin etme.\n"
    "2) Bağlam soruyu yanıtlamıyorsa tek cümleyle 'Bu bilgi repo içeriklerinde yok.' de "
    "ve gerekirse hangi bilgiyle sorulabileceğini öner.\n"
    "3) Sayıları, sürümleri, isimleri ve teknik terimleri aynen aktar; kod/komutları "
    "``` bloğunda ver.\n"
    "4) Bağlam İngilizce olsa da cevabı Türkçe yaz.\n"
    "5) Format: 1-2 cümlelik özet, sonra kısa madde işaretleri. Giriş/kapanış cümlesi, "
    "özür ve tekrar yok. Gerekmedikçe 150 kelimeyi aşma.\n"
    "6) Soruda geçen 'bu repo/proje' ifadesi bağlamdaki 'Kaynak' repoyu kasteder."
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
    "Aşağıdaki web arama sonuçlarına dayanarak soruyu yanıtla. Sonuçlar soruyla "
    "gerçekten ilgili değilse (başka bir konu/kişi hakkındaysa) uydurma; "
    "'Uygun bir kaynak bulunamadı.' de. 'Kaynak 1/2' gibi etiketleri cevapta anma; "
    "bilgiyi doğrudan aktar.\n\n"
    "{context}\n\n"
    "Soru: {soru}\n\n"
    "Yanıt:"
)
