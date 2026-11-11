import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';
import 'package:url_launcher/url_launcher.dart';

import 'rides_screen.dart';

class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});

  void _open(BuildContext context, Widget page) => Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));

  @override
  Widget build(BuildContext context) {
    final user = AuthScope.of(context).user;
    return Scaffold(
      appBar: AppBar(title: const Text('More')),
      body: ListView(padding: const EdgeInsets.all(12), children: [
        Card(
          child: Column(children: [
            ListTile(leading: const Icon(Icons.payments_outlined), title: const Text('Payments'), trailing: const Icon(Icons.chevron_right),
                onTap: () => _open(context, const RidesScreen(payments: true))),
            ListTile(leading: const Icon(Icons.bar_chart), title: const Text('Daily reports'), trailing: const Icon(Icons.chevron_right),
                onTap: () => _open(context, const ReportsScreen())),
            ListTile(leading: const Icon(Icons.mail_outline), title: const Text('Contact messages'), trailing: const Icon(Icons.chevron_right),
                onTap: () => _open(context, const MessagesScreen())),
            ListTile(leading: const Icon(Icons.manage_accounts_outlined), title: const Text('My account'), subtitle: Text(user?.email ?? ''),
                trailing: const Icon(Icons.chevron_right), onTap: () => _open(context, const _AdminAccountPage())),
          ]),
        ),
      ]),
    );
  }
}

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key});

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  List<dynamic>? _rows;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    try {
      final rows = await AuthScope.read(context).api.get('/admin/reports/') as List;
      if (mounted) setState(() => _rows = rows);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final rows = _rows;
    return Scaffold(
      appBar: AppBar(title: const Text('Daily reports')),
      body: rows == null
          ? Center(child: _error != null ? ErrorBanner(_error, onRetry: _load) : const CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: rows.isEmpty
                  ? ListView(children: const [EmptyState('No ride data yet.')])
                  : ListView.separated(
                      padding: const EdgeInsets.all(12),
                      itemCount: rows.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (context, i) {
                        final r = rows[i] as Map<String, dynamic>;
                        return Card(
                          child: ListTile(
                            title: Text(formatDay(DateTime.tryParse(r['date'].toString()))),
                            subtitle: Text('${r['total_rides']} rides · ${r['completed_rides']} completed · ${r['cancelled_rides']} cancelled'),
                            trailing: Text(money(toDouble(r['total_revenue'])), style: const TextStyle(fontWeight: FontWeight.w700)),
                          ),
                        );
                      },
                    ),
            ),
    );
  }
}

class _Message {
  _Message(Map<String, dynamic> j)
      : id = j['id'] as int,
        name = str(j['name']),
        email = str(j['email']),
        message = str(j['message']),
        createdAt = toDate(j['created_at']);

  final int id;
  final String name;
  final String email;
  final String message;
  final DateTime? createdAt;
}

class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key});

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  final _list = GlobalKey<PagedListViewState<_Message>>();

  Future<void> _delete(_Message m) async {
    if (!await confirmDialog(context, 'Delete message?', 'From ${m.name}', action: 'Delete')) return;
    if (!mounted) return;
    try {
      await AuthScope.read(context).api.delete('/admin/messages/${m.id}/');
      _list.currentState?.updateWhere((x) => x.id == m.id, null);
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = AuthScope.read(context).api;
    return Scaffold(
      appBar: AppBar(title: const Text('Contact messages')),
      body: PagedListView<_Message>(
        key: _list,
        emptyText: 'No messages.',
        load: (page) async => PageOf.fromJson(await api.get('/admin/messages/', query: {'page': '$page'}), _Message.new),
        itemBuilder: (context, m) => Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(m.name, style: const TextStyle(fontWeight: FontWeight.w700))),
                Text(formatWhen(m.createdAt), style: const TextStyle(color: Colors.white54, fontSize: 12)),
              ]),
              const SizedBox(height: 6),
              Text(m.message),
              Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                TextButton.icon(
                  onPressed: () => launchUrl(Uri(scheme: 'mailto', path: m.email)),
                  icon: const Icon(Icons.reply),
                  label: const Text('Reply'),
                ),
                IconButton(onPressed: () => _delete(m), icon: const Icon(Icons.delete_outline), tooltip: 'Delete'),
              ]),
            ]),
          ),
        ),
      ),
    );
  }
}

class _AdminAccountPage extends StatelessWidget {
  const _AdminAccountPage();

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('My account')),
        body: const AccountScreen(extra: [_CreateAdminCard()]),
      );
}

class _CreateAdminCard extends StatefulWidget {
  const _CreateAdminCard();

  @override
  State<_CreateAdminCard> createState() => _CreateAdminCardState();
}

class _CreateAdminCardState extends State<_CreateAdminCard> {
  final _c = {for (final k in ['full_name', 'username', 'email', 'password']) k: TextEditingController()};
  bool _busy = false;

  @override
  void dispose() {
    for (final c in _c.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _create() async {
    if (_c.values.any((c) => c.text.trim().isEmpty)) {
      showSnack(context, 'Fill in all fields.', error: true);
      return;
    }
    setState(() => _busy = true);
    try {
      final json = await AuthScope.read(context).api.post('/admin/admins/', {for (final e in _c.entries) e.key: e.value.text.trim()});
      for (final c in _c.values) {
        c.clear();
      }
      if (mounted) showSnack(context, 'Admin created: ${(json as Map)['email']}');
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text('Add another admin', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(controller: _c['full_name'], decoration: const InputDecoration(labelText: 'Full name')),
            const SizedBox(height: 8),
            TextField(controller: _c['username'], decoration: const InputDecoration(labelText: 'Username')),
            const SizedBox(height: 8),
            TextField(controller: _c['email'], keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email')),
            const SizedBox(height: 8),
            TextField(controller: _c['password'], obscureText: true, decoration: const InputDecoration(labelText: 'Temporary password')),
            const SizedBox(height: 12),
            FilledButton.tonal(onPressed: _busy ? null : _create, child: Text(_busy ? 'Creating…' : 'Create admin')),
          ]),
        ),
      );
}
