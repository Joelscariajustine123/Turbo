import 'dart:async';

import 'package:flutter/material.dart';

import 'models.dart';

// ---------------------------------------------------------------- formatting

/// Human-readable message for any error (drops Dart's "Exception: " prefix).
String errorText(Object e) => e.toString().replaceFirst(RegExp(r'^Exception: '), '');

String money(num? v) {
  final value = (v ?? 0).toDouble();
  final parts = value.toStringAsFixed(2).split('.');
  final whole = parts[0];
  // Indian grouping: 12,34,567.89
  String grouped;
  if (whole.length <= 3) {
    grouped = whole;
  } else {
    final last3 = whole.substring(whole.length - 3);
    var rest = whole.substring(0, whole.length - 3);
    final groups = <String>[];
    while (rest.length > 2) {
      groups.insert(0, rest.substring(rest.length - 2));
      rest = rest.substring(0, rest.length - 2);
    }
    if (rest.isNotEmpty) groups.insert(0, rest);
    grouped = '${groups.join(',')},$last3';
  }
  return '₹$grouped.${parts[1]}';
}

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

String two(int n) => n.toString().padLeft(2, '0');

String formatDay(DateTime? d) => d == null ? '—' : '${two(d.day)} ${_months[d.month - 1]} ${d.year}';

String formatWhen(DateTime? d) => d == null ? '—' : '${two(d.day)} ${_months[d.month - 1]}, ${two(d.hour)}:${two(d.minute)}';

String shortDay(DateTime d) => '${two(d.day)} ${_months[d.month - 1]}';

// ---------------------------------------------------------------- theme

// Only colour-scheme level theming, so it compiles on every Flutter 3.22+ release
// (component theme classes such as CardTheme were renamed in later versions).
ThemeData turboTheme(Color seed) {
  final scheme = ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: const Color(0xFF0F0F10),
  );
}

// ---------------------------------------------------------------- small widgets

const statusColors = {
  'PENDING': Color(0xFF52525B),
  'CONFIRMED': Color(0xFF0E7490),
  'ACCEPTED': Color(0xFF1D4ED8),
  'ARRIVED': Color(0xFF7C3AED),
  'IN_PROGRESS': Color(0xFF1D4ED8),
  'COMPLETED': Color(0xFF15803D),
  'CANCELLED': Color(0xFFB91C1C),
};

class StatusChip extends StatelessWidget {
  const StatusChip(this.status, this.label, {super.key});

  final String status;
  final String label;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
        decoration: BoxDecoration(
          color: statusColors[status] ?? Colors.grey.shade700,
          borderRadius: BorderRadius.circular(99),
        ),
        child: Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.white)),
      );
}

class ErrorBanner extends StatelessWidget {
  const ErrorBanner(this.message, {super.key, this.onRetry});

  final String? message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    if (message == null || message!.isEmpty) return const SizedBox.shrink();
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: scheme.errorContainer, borderRadius: BorderRadius.circular(10)),
      child: Row(children: [
        Icon(Icons.error_outline, color: scheme.onErrorContainer),
        const SizedBox(width: 10),
        Expanded(child: Text(message!, style: TextStyle(color: scheme.onErrorContainer))),
        if (onRetry != null) TextButton(onPressed: onRetry, child: const Text('Retry')),
      ]),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState(this.text, {super.key, this.icon = Icons.inbox_outlined});

  final String text;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 48, color: Colors.white24),
          const SizedBox(height: 12),
          Text(text, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white54)),
        ]),
      );
}

class StatCard extends StatelessWidget {
  const StatCard(this.label, this.value, {super.key, this.hint});

  final String label;
  final String value;
  final String? hint;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text(label, style: const TextStyle(color: Colors.white60, fontSize: 13)),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
            if (hint != null) Text(hint!, style: const TextStyle(color: Colors.white38, fontSize: 12)),
          ]),
        ),
      );
}

/// Two-column grid of [StatCard]s that sizes itself to its content.
class StatGrid extends StatelessWidget {
  const StatGrid(this.cards, {super.key});

  final List<Widget> cards;

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
        final w = (c.maxWidth - 10) / 2;
        return Wrap(spacing: 10, runSpacing: 10, children: [for (final card in cards) SizedBox(width: w, child: card)]);
      });
}

/// Simple vertical bar chart (no chart package needed).
class BarChart extends StatelessWidget {
  const BarChart({super.key, required this.labels, required this.values, this.height = 180});

  final List<String> labels;
  final List<double> values;
  final double height;

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return const EmptyState('No data to chart yet.', icon: Icons.bar_chart);
    final max = values.reduce((a, b) => a > b ? a : b);
    final color = Theme.of(context).colorScheme.primary;
    return SizedBox(
      height: height + 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: values.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, i) => SizedBox(
          width: 38,
          child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
            Text('₹${values[i].round()}', style: const TextStyle(fontSize: 9, color: Colors.white54)),
            const SizedBox(height: 2),
            Container(
              height: max <= 0 ? 2 : (values[i] / max * height).clamp(2, height).toDouble(),
              decoration: BoxDecoration(color: color, borderRadius: const BorderRadius.vertical(top: Radius.circular(4))),
            ),
            const SizedBox(height: 4),
            Text(labels[i], style: const TextStyle(fontSize: 9, color: Colors.white54), maxLines: 1),
          ]),
        ),
      ),
    );
  }
}

void showSnack(BuildContext context, String message, {bool error = false}) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: error ? Theme.of(context).colorScheme.error : null,
    ));
}

Future<bool> confirmDialog(BuildContext context, String title, String message, {String action = 'Yes'}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('No')),
        FilledButton(onPressed: () => Navigator.pop(c, true), child: Text(action)),
      ],
    ),
  );
  return ok == true;
}

// ---------------------------------------------------------------- paged list

/// Pull-to-refresh list that loads more pages as you scroll.
/// Give it a `GlobalKey<PagedListViewState<T>>` to call `refresh()` from outside.
class PagedListView<T> extends StatefulWidget {
  const PagedListView({
    super.key,
    required this.load,
    required this.itemBuilder,
    this.emptyText = 'Nothing here yet.',
    this.pollEvery,
    this.header,
    this.padding = const EdgeInsets.all(12),
  });

  final Future<PageOf<T>> Function(int page) load;
  final Widget Function(BuildContext context, T item) itemBuilder;
  final String emptyText;
  final Duration? pollEvery;
  final Widget? header;
  final EdgeInsets padding;

  @override
  State<PagedListView<T>> createState() => PagedListViewState<T>();
}

class PagedListViewState<T> extends State<PagedListView<T>> {
  final _items = <T>[];
  int _page = 0;
  bool _hasMore = true;
  bool _loading = false;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    refresh();
    if (widget.pollEvery != null) {
      _timer = Timer.periodic(widget.pollEvery!, (_) => refresh(quiet: true));
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> refresh({bool quiet = false}) async {
    if (!quiet) setState(() => _error = null);
    try {
      final first = await widget.load(1);
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(first.results);
        _page = 1;
        _hasMore = first.hasNext;
        _error = null;
      });
    } catch (e) {
      if (mounted && !quiet) setState(() => _error = errorText(e));
    }
  }

  Future<void> _loadMore() async {
    if (_loading || !_hasMore) return;
    setState(() => _loading = true);
    try {
      final next = await widget.load(_page + 1);
      if (!mounted) return;
      setState(() {
        _items.addAll(next.results);
        _page += 1;
        _hasMore = next.hasNext;
      });
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  /// Replace or remove an item after an edit without reloading.
  void updateWhere(bool Function(T) test, T? replacement) {
    setState(() {
      final i = _items.indexWhere(test);
      if (i < 0) return;
      if (replacement == null) {
        _items.removeAt(i);
      } else {
        _items[i] = replacement;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[
      if (widget.header != null) widget.header!,
      if (_error != null) Padding(padding: const EdgeInsets.only(bottom: 10), child: ErrorBanner(_error, onRetry: refresh)),
      if (_items.isEmpty && _error == null && _page == 0) const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
      if (_items.isEmpty && _page > 0) EmptyState(widget.emptyText),
    ];
    return RefreshIndicator(
      onRefresh: refresh,
      child: NotificationListener<ScrollNotification>(
        onNotification: (n) {
          if (n.metrics.pixels > n.metrics.maxScrollExtent - 300) _loadMore();
          return false;
        },
        child: ListView.separated(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: widget.padding,
          itemCount: children.length + _items.length + (_hasMore && _items.isNotEmpty ? 1 : 0),
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (context, i) {
            if (i < children.length) return children[i];
            final idx = i - children.length;
            if (idx >= _items.length) {
              return const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator()));
            }
            return widget.itemBuilder(context, _items[idx]);
          },
        ),
      ),
    );
  }
}
