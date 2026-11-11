import 'dart:async';

import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';

/// Search box that rebuilds its list after typing pauses.
class _SearchBar extends StatefulWidget {
  const _SearchBar({required this.hint, required this.onChanged});

  final String hint;
  final ValueChanged<String> onChanged;

  @override
  State<_SearchBar> createState() => _SearchBarState();
}

class _SearchBarState extends State<_SearchBar> {
  Timer? _t;

  @override
  void dispose() {
    _t?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 4),
        child: TextField(
          decoration: InputDecoration(hintText: widget.hint, prefixIcon: const Icon(Icons.search), isDense: true),
          onChanged: (v) {
            _t?.cancel();
            _t = Timer(const Duration(milliseconds: 400), () => widget.onChanged(v.trim()));
          },
        ),
      );
}

// ---------------------------------------------------------------- riders

class RidersScreen extends StatefulWidget {
  const RidersScreen({super.key});

  @override
  State<RidersScreen> createState() => _RidersScreenState();
}

class _RidersScreenState extends State<RidersScreen> {
  String _search = '';
  int _version = 0;

  Future<void> _edit(User rider) async {
    final api = AuthScope.read(context).api;
    final changed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _RiderSheet(rider: rider, api: api),
    );
    if (changed == true) setState(() => _version++);
  }

  @override
  Widget build(BuildContext context) {
    final api = AuthScope.read(context).api;
    return Scaffold(
      appBar: AppBar(title: const Text('Riders')),
      body: Column(children: [
        _SearchBar(hint: 'Search name, email, phone', onChanged: (v) => setState(() => _search = v)),
        Expanded(
          child: PagedListView<User>(
            key: ValueKey('$_search|$_version'),
            emptyText: 'No riders found.',
            load: (page) async => PageOf.fromJson(
              await api.get('/admin/riders/', query: {'page': '$page', 'search': _search}),
              User.fromJson,
            ),
            itemBuilder: (context, u) => Card(
              child: ListTile(
                onTap: () => _edit(u),
                leading: CircleAvatar(child: Text(u.fullName.isEmpty ? '?' : u.fullName[0])),
                title: Text(u.fullName, style: TextStyle(color: u.isActive ? null : Colors.white38)),
                subtitle: Text('${u.email}\n${u.phone} · joined ${formatDay(u.dateJoined)}'),
                isThreeLine: true,
                trailing: u.isActive ? const Icon(Icons.chevron_right) : const Text('Inactive', style: TextStyle(color: Colors.redAccent)),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

class _RiderSheet extends StatefulWidget {
  const _RiderSheet({required this.rider, required this.api});

  final User rider;
  final ApiClient api;

  @override
  State<_RiderSheet> createState() => _RiderSheetState();
}

class _RiderSheetState extends State<_RiderSheet> {
  late final _name = TextEditingController(text: widget.rider.fullName);
  late final _email = TextEditingController(text: widget.rider.email);
  late final _phone = TextEditingController(text: widget.rider.phone);
  late bool _active = widget.rider.isActive;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.patch('/admin/riders/${widget.rider.id}/', {
        'full_name': _name.text.trim(),
        'email': _email.text.trim(),
        'phone': _phone.text.trim(),
        'is_active': _active,
      });
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _delete() async {
    if (!await confirmDialog(context, 'Delete rider?', 'This deletes ${widget.rider.fullName} and all their rides.', action: 'Delete')) return;
    setState(() => _busy = true);
    try {
      await widget.api.delete('/admin/riders/${widget.rider.id}/');
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Edit rider', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          ErrorBanner(_error),
          const SizedBox(height: 8),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Full name')),
          const SizedBox(height: 8),
          TextField(controller: _email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email')),
          const SizedBox(height: 8),
          TextField(controller: _phone, keyboardType: TextInputType.phone, maxLength: 10, decoration: const InputDecoration(labelText: 'Phone', counterText: '')),
          SwitchListTile(value: _active, onChanged: (v) => setState(() => _active = v), title: const Text('Account active'), contentPadding: EdgeInsets.zero),
          const SizedBox(height: 8),
          Row(children: [
            TextButton.icon(
              onPressed: _busy ? null : _delete,
              style: TextButton.styleFrom(foregroundColor: Colors.redAccent),
              icon: const Icon(Icons.delete_outline),
              label: const Text('Delete'),
            ),
            const Spacer(),
            FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save')),
          ]),
        ]),
      );
}

// ---------------------------------------------------------------- drivers

class DriversScreen extends StatefulWidget {
  const DriversScreen({super.key});

  @override
  State<DriversScreen> createState() => _DriversScreenState();
}

class _DriversScreenState extends State<DriversScreen> {
  String _search = '';
  int _version = 0;

  Future<void> _manage(DriverProfile d) async {
    final auth = AuthScope.read(context);
    final meta = await auth.meta();
    if (!mounted) return;
    final changed = await showModalBottomSheet<bool>(
      context: context,
      builder: (_) => _DriverSheet(driver: d, api: auth.api, availability: meta.availability),
    );
    if (changed == true) setState(() => _version++);
  }

  @override
  Widget build(BuildContext context) {
    final api = AuthScope.read(context).api;
    return Scaffold(
      appBar: AppBar(title: const Text('Drivers')),
      body: Column(children: [
        _SearchBar(hint: 'Search name, vehicle, licence', onChanged: (v) => setState(() => _search = v)),
        Expanded(
          child: PagedListView<DriverProfile>(
            key: ValueKey('$_search|$_version'),
            emptyText: 'No drivers found.',
            load: (page) async => PageOf.fromJson(
              await api.get('/admin/drivers/', query: {'page': '$page', 'search': _search}),
              DriverProfile.fromJson,
            ),
            itemBuilder: (context, d) => Card(
              child: ListTile(
                onTap: () => _manage(d),
                leading: CircleAvatar(
                  backgroundImage: d.photo != null ? NetworkImage(d.photo!) : null,
                  child: d.photo == null ? Text(d.fullName.isEmpty ? '?' : d.fullName[0]) : null,
                ),
                title: Text(d.fullName, style: TextStyle(color: d.isActive ? null : Colors.white38)),
                subtitle: Text('${d.vehicleInfo.isEmpty ? 'No vehicle added' : d.vehicleInfo}\n${d.phone} · ${d.email}'),
                isThreeLine: true,
                trailing: Text(d.isActive ? d.availabilityDisplay : 'Inactive',
                    style: TextStyle(color: d.isActive ? Colors.white70 : Colors.redAccent)),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

class _DriverSheet extends StatefulWidget {
  const _DriverSheet({required this.driver, required this.api, required this.availability});

  final DriverProfile driver;
  final ApiClient api;
  final List<Choice> availability;

  @override
  State<_DriverSheet> createState() => _DriverSheetState();
}

class _DriverSheetState extends State<_DriverSheet> {
  late String _availability = widget.driver.availability;
  late bool _active = widget.driver.isActive;
  bool _busy = false;
  String? _error;

  Future<void> _run(Future<void> Function() fn) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await fn();
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.driver;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text(d.fullName, style: Theme.of(context).textTheme.titleLarge),
        Text('${d.email} · ${d.phone}', style: const TextStyle(color: Colors.white60)),
        Text('Licence ${d.licenseNumber.isEmpty ? '—' : d.licenseNumber} · ${d.vehicleInfo.isEmpty ? 'no vehicle' : d.vehicleInfo}',
            style: const TextStyle(color: Colors.white60)),
        const SizedBox(height: 12),
        ErrorBanner(_error),
        const SizedBox(height: 8),
        DropdownButtonFormField<String>(
          // `value` keeps Flutter 3.22–3.32 support (`initialValue` only exists from 3.33).
          // ignore: deprecated_member_use
          value: _availability,
          decoration: const InputDecoration(labelText: 'Availability'),
          items: [for (final a in widget.availability) DropdownMenuItem(value: a.value, child: Text(a.label))],
          onChanged: (v) => setState(() => _availability = v ?? _availability),
        ),
        SwitchListTile(value: _active, onChanged: (v) => setState(() => _active = v), title: const Text('Account active'), contentPadding: EdgeInsets.zero),
        Row(children: [
          TextButton.icon(
            onPressed: _busy
                ? null
                : () async {
                    if (await confirmDialog(context, 'Delete driver?', 'This deletes ${d.fullName}\'s account.', action: 'Delete')) {
                      await _run(() => widget.api.delete('/admin/drivers/${d.id}/'));
                    }
                  },
            style: TextButton.styleFrom(foregroundColor: Colors.redAccent),
            icon: const Icon(Icons.delete_outline),
            label: const Text('Delete'),
          ),
          const Spacer(),
          FilledButton(
            onPressed: _busy
                ? null
                : () => _run(() => widget.api.patch('/admin/drivers/${d.id}/', {'availability_status': _availability, 'is_active': _active})),
            child: Text(_busy ? 'Saving…' : 'Save'),
          ),
        ]),
      ]),
    );
  }
}
