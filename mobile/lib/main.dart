import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'api_service.dart';

void main() {
  runApp(const ChatAsistanApp());
}

// --- Apple / iMessage tarzı renk paleti (açık tema) ---
const Color _appleBlue = Color(0xFF007AFF);
const Color _asstGray = Color(0xFFE9E9EB);
const Color _bg = Color(0xFFFFFFFF);
const Color _text = Color(0xFF1C1C1E);
const Color _muted = Color(0xFF8E8E93);
const Color _border = Color(0xFFE5E5EA);
const Color _warn = Color(0xFFFF9500);
const Color _warnBg = Color(0xFFFFF1DE);
const Color _success = Color(0xFF34C759);

class ChatAsistanApp extends StatelessWidget {
  const ChatAsistanApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CV Asistanı',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.light,
        scaffoldBackgroundColor: _bg,
        colorScheme: const ColorScheme.light(
          primary: _appleBlue,
          surface: _bg,
          onSurface: _text,
        ),
        textTheme: GoogleFonts.interTextTheme(ThemeData.light().textTheme),
        appBarTheme: const AppBarTheme(
          backgroundColor: _bg,
          foregroundColor: _text,
          elevation: 0,
          scrolledUnderElevation: 0,
        ),
      ),
      home: const ChatScreen(),
    );
  }
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _busy = false;

  static const List<String> _sampleQuestions = [
    "telco-churn-project nasıl bir proje?",
    "HizmetGelsin'in teknolojileri neler?",
    "bilgitr-rag-projesi ne yapıyor?",
    "hangi dillerde yazılmış?",
  ];

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOutCubic,
      );
    });
  }

  Future<void> _send(String text) async {
    final soru = text.trim();
    if (soru.isEmpty || _busy) return; // çift gönderimi engelle

    setState(() {
      _messages.add(ChatMessage.user(soru));
      _busy = true;
    });
    _controller.clear();
    _scrollToBottom();

    try {
      final response = await sendQuestion(soru);
      if (!mounted) return;
      setState(() => _messages.add(ChatMessage.assistant(response)));
    } on ChatApiException catch (e) {
      if (!mounted) return;
      setState(() => _messages.add(ChatMessage.error(e.message)));
    } catch (e) {
      if (!mounted) return;
      setState(() => _messages.add(ChatMessage.error('Beklenmeyen bir hata: $e')));
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        _scrollToBottom();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: _buildAppBar(),
      body: Column(
        children: [
          _buildChips(),
          const Divider(height: 1, thickness: 0.5, color: _border),
          Expanded(child: _buildMessageArea()),
          _buildInputBar(),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      toolbarHeight: 64,
      titleSpacing: 20,
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            'CV Asistanı',
            style: GoogleFonts.inter(
              fontSize: 22,
              fontWeight: FontWeight.w700,
              color: _text,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 1),
          Text(
            "Abdulkadir'in projeleri hakkında sor",
            style: GoogleFonts.inter(fontSize: 13, color: _muted),
          ),
        ],
      ),
      bottom: const PreferredSize(
        preferredSize: Size.fromHeight(1),
        child: Divider(height: 1, thickness: 0.5, color: _border),
      ),
    );
  }

  Widget _buildChips() {
    return Container(
      width: double.infinity,
      color: const Color(0xFFF9F9FB),
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'ÖNERİLEN SORULAR',
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: _muted,
              letterSpacing: 0.6,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final q in _sampleQuestions)
                _SuggestionChip(
                  label: q,
                  enabled: !_busy,
                  onTap: () => _send(q),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMessageArea() {
    if (_messages.isEmpty && !_busy) {
      return const _EmptyState();
    }
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      itemCount: _messages.length + (_busy ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _messages.length) {
          return const _TypingBubble();
        }
        return _AnimatedMessageBubble(message: _messages[index]);
      },
    );
  }

  Widget _buildInputBar() {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        decoration: const BoxDecoration(
          color: _bg,
          border: Border(top: BorderSide(color: _border, width: 0.5)),
        ),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _controller,
                enabled: !_busy,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(_controller.text),
                style: GoogleFonts.inter(fontSize: 16, color: _text),
                decoration: InputDecoration(
                  hintText: 'Mesaj',
                  hintStyle: GoogleFonts.inter(fontSize: 16, color: _muted),
                  filled: true,
                  fillColor: const Color(0xFFF2F2F7),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: _border),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: _border),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: _appleBlue, width: 1.2),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              onPressed: _busy ? null : () => _send(_controller.text),
              icon: const Icon(Icons.arrow_upward_rounded, color: Colors.white),
              tooltip: 'Gönder',
              style: IconButton.styleFrom(
                backgroundColor: _busy ? _border : _appleBlue,
                disabledBackgroundColor: _border,
                shape: const CircleBorder(),
                padding: const EdgeInsets.all(10),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Bir sohbet mesajı: kullanıcı / asistan / hata.
class ChatMessage {
  final String text;
  final bool isUser;
  final bool isError;
  final ChatResponse? response; // yalnızca asistan mesajında dolu

  ChatMessage.user(this.text)
      : isUser = true,
        isError = false,
        response = null;

  ChatMessage.assistant(ChatResponse this.response)
      : text = response.cevap,
        isUser = false,
        isError = false;

  ChatMessage.error(this.text)
      : isUser = false,
        isError = true,
        response = null;
}

/// Yeni mesaj geldiğinde hafif bir fade + slide animasyonu yapar.
class _AnimatedMessageBubble extends StatelessWidget {
  final ChatMessage message;

  const _AnimatedMessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 260),
      curve: Curves.easeOutCubic,
      builder: (context, value, child) {
        return Opacity(
          opacity: value,
          child: Transform.translate(
            offset: Offset(0, (1 - value) * 12),
            child: child,
          ),
        );
      },
      child: _MessageBubble(message: message),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final ChatMessage message;

  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final isError = message.isError;
    final crossAxisAlignment =
        isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Column(
        crossAxisAlignment: crossAxisAlignment,
        children: [
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.75,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 11),
            decoration: BoxDecoration(
              color: isUser
                  ? _appleBlue
                  : isError
                      ? _warnBg
                      : _asstGray,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(20),
                topRight: const Radius.circular(20),
                bottomLeft: Radius.circular(isUser ? 20 : 6),
                bottomRight: Radius.circular(isUser ? 6 : 20),
              ),
            ),
            child: Text(
              message.text,
              style: GoogleFonts.inter(
                fontSize: 16,
                height: 1.4,
                color: isUser ? Colors.white : (isError ? const Color(0xFF7A3D00) : _text),
              ),
            ),
          ),
          // Asistan cevabının altındaki kaynak/doğrulama rozeti
          if (!isUser && !isError && message.response != null)
            Padding(
              padding: const EdgeInsets.only(top: 6, left: 2),
              child: _MetaBadge(response: message.response!),
            ),
        ],
      ),
    );
  }
}

/// Kaynak + doğrulama durumunu gösteren zarif bir "pill" (hap) rozeti.
class _MetaBadge extends StatelessWidget {
  final ChatResponse response;

  const _MetaBadge({required this.response});

  @override
  Widget build(BuildContext context) {
    final verified = response.dogrulandi;
    final sure = response.sureSaniye.toStringAsFixed(1);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: verified ? const Color(0xFFF2F2F7) : _warnBg,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: verified ? _border : _warn.withValues(alpha: 0.45),
          width: 0.5,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            verified ? Icons.check_circle_rounded : Icons.error_rounded,
            size: 13,
            color: verified ? _success : _warn,
          ),
          const SizedBox(width: 4),
          Text(
            verified
                ? 'Doğrulandı · ${response.kaynak} · ${sure}sn'
                : 'Doğrulanmadı · ${response.kaynak}',
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: verified ? _muted : const Color(0xFFB25E00),
            ),
          ),
        ],
      ),
    );
  }
}

/// Hiç mesaj yokken gösterilen karşılama ekranı.
class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: const BoxDecoration(
                color: Color(0xFFF2F2F7),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.chat_bubble_outline_rounded,
                  size: 40, color: _appleBlue),
            ),
            const SizedBox(height: 20),
            Text(
              'Merhaba! Projelerim hakkında bana soru sorabilirsin.',
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(fontSize: 17, color: _text, height: 1.4),
            ),
          ],
        ),
      ),
    );
  }
}

/// Asistan balonu şeklinde, içinde zıplayan üç nokta olan "yazıyor..." göstergesi.
class _TypingBubble extends StatefulWidget {
  const _TypingBubble();

  @override
  State<_TypingBubble> createState() => _TypingBubbleState();
}

class _TypingBubbleState extends State<_TypingBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1100),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: const BoxDecoration(
          color: _asstGray,
          borderRadius: BorderRadius.only(
            topLeft: Radius.circular(20),
            topRight: Radius.circular(20),
            bottomRight: Radius.circular(20),
            bottomLeft: Radius.circular(6),
          ),
        ),
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            return Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(3, (i) {
                final phase = (_controller.value * 2 * math.pi) - (i * 0.9);
                final dy = -math.sin(phase).abs() * 3.0;
                return Transform.translate(
                  offset: Offset(0, dy),
                  child: Container(
                    width: 7,
                    height: 7,
                    margin: const EdgeInsets.symmetric(horizontal: 2.5),
                    decoration: const BoxDecoration(
                      color: _muted,
                      shape: BoxShape.circle,
                    ),
                  ),
                );
              }),
            );
          },
        ),
      ),
    );
  }
}

/// Dokunulduğunda hafif basılma animasyonu yapan öneri chip'i.
class _SuggestionChip extends StatefulWidget {
  final String label;
  final bool enabled;
  final VoidCallback onTap;

  const _SuggestionChip({
    required this.label,
    required this.enabled,
    required this.onTap,
  });

  @override
  State<_SuggestionChip> createState() => _SuggestionChipState();
}

class _SuggestionChipState extends State<_SuggestionChip> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: widget.enabled ? widget.onTap : null,
      child: AnimatedScale(
        scale: _pressed ? 0.95 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: AnimatedOpacity(
          opacity: widget.enabled ? 1.0 : 0.5,
          duration: const Duration(milliseconds: 150),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: _border),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x0A000000),
                  blurRadius: 4,
                  offset: Offset(0, 1),
                ),
              ],
            ),
            child: Text(
              widget.label,
              style: GoogleFonts.inter(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: _appleBlue,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
