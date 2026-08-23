import 'dart:convert';

import 'package:http/http.dart' as http;

/// Backend API'nin temel adresi.
///
/// Canlı demo Hugging Face Spaces'ta barınıyor; bu adres her yerden
/// (gerçek cihaz, web vb.) erişilebilir.
const String apiBaseUrl = 'https://akadirgok-github-asistani.hf.space';

/// `/chat` uç noktasının döndürdüğü yanıtı temsil eden model.
class ChatResponse {
  final String cevap;
  final String kaynak;
  final bool dogrulandi;
  final double sureSaniye;

  ChatResponse({
    required this.cevap,
    required this.kaynak,
    required this.dogrulandi,
    required this.sureSaniye,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    return ChatResponse(
      cevap: json['cevap'] as String? ?? '',
      kaynak: json['kaynak'] as String? ?? '?',
      dogrulandi: json['dogrulandi'] as bool? ?? false,
      sureSaniye: (json['sure_saniye'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

/// API çağrısı sırasında oluşan hataları temsil eden basit istisna.
///
/// Mesaj doğrudan kullanıcıya gösterilebilecek kadar açıklayıcıdır.
class ChatApiException implements Exception {
  final String message;

  ChatApiException(this.message);

  @override
  String toString() => message;
}

/// Soruyu backend `/chat` uç noktasına gönderir ve yanıtı döndürür.
///
/// Sunucuya ulaşılamazsa (kapalı, ağ hatası, yanlış IP vb.) ya da sunucu hata
/// döndürürse [ChatApiException] fırlatır; uygulama çökmez, çağıran taraf hatayı
/// yakalayıp gösterir.
Future<ChatResponse> sendQuestion(String soru) async {
  final uri = Uri.parse('$apiBaseUrl/chat');

  final http.Response response;
  try {
    response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'soru': soru}),
        )
        // Model 20-60 saniye sürebilir; yeterli bir zaman aşımı bırak.
        .timeout(const Duration(seconds: 120));
  } catch (_) {
    throw ChatApiException(
      'Sunucuya ulaşılamadı. Backend\'in çalıştığından emin olun.',
    );
  }

  if (response.statusCode != 200) {
    throw ChatApiException(
      'Sunucu hata döndürdü (HTTP ${response.statusCode}).',
    );
  }

  // Türkçe karakterlerin bozulmaması için bodyBytes'i UTF-8 ile çöz.
  final decoded = jsonDecode(utf8.decode(response.bodyBytes));
  return ChatResponse.fromJson(decoded as Map<String, dynamic>);
}
