import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:turbo_core/turbo_core.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _form = GlobalKey<FormState>();
  final _c = {
    for (final k in ['full_name', 'phone', 'email', 'license_number', 'vehicle_info']) k: TextEditingController(),
  };
  DriverProfile? _profile;
  String? _photoPath;
  String? _error;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    for (final c in _c.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _fill(DriverProfile p) {
    _profile = p;
    _c['full_name']!.text = p.fullName;
    _c['phone']!.text = p.phone;
    _c['email']!.text = p.email;
    _c['license_number']!.text = p.licenseNumber;
    _c['vehicle_info']!.text = p.vehicleInfo;
  }

  Future<void> _load() async {
    try {
      final json = await AuthScope.read(context).api.get('/driver/profile/');
      if (mounted) setState(() => _fill(DriverProfile.fromJson(json as Map<String, dynamic>)));
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    }
  }

  Future<void> _pickPhoto() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (c) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(Icons.photo_camera), title: const Text('Take a photo'), onTap: () => Navigator.pop(c, ImageSource.camera)),
          ListTile(leading: const Icon(Icons.photo_library), title: const Text('Choose from gallery'), onTap: () => Navigator.pop(c, ImageSource.gallery)),
        ]),
      ),
    );
    if (source == null) return;
    final file = await ImagePicker().pickImage(source: source, maxWidth: 800, imageQuality: 85);
    if (file != null && mounted) setState(() => _photoPath = file.path);
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final auth = AuthScope.read(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final fields = {for (final e in _c.entries) e.key: e.value.text.trim()};
      final json = await auth.api.multipart('PATCH', '/driver/profile/', fields,
          fileField: _photoPath != null ? 'profile_photo' : null, filePath: _photoPath);
      await auth.reloadUser();
      if (!mounted) return;
      setState(() {
        _fill(DriverProfile.fromJson(json as Map<String, dynamic>));
        _photoPath = null;
      });
      showSnack(context, 'Profile saved.');
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _field(String key, String label, {TextInputType? type, String? Function(String?)? validator, int? maxLength}) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: TextFormField(
          controller: _c[key],
          keyboardType: type,
          maxLength: maxLength,
          decoration: InputDecoration(labelText: label, counterText: ''),
          validator: validator ?? ((v) => (v == null || v.trim().isEmpty) ? 'Required' : null),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final p = _profile;
    final ImageProvider? avatar = p?.photo != null ? NetworkImage(p!.photo!) : null;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: p == null
          ? Center(child: _error != null ? ErrorBanner(_error, onRetry: _load) : const CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.all(16), children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Form(
                    key: _form,
                    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      Center(
                        child: Stack(children: [
                          CircleAvatar(
                            radius: 44,
                            backgroundImage: avatar,
                            child: avatar == null ? Text(p.fullName.isEmpty ? '?' : p.fullName[0], style: const TextStyle(fontSize: 32)) : null,
                          ),
                          Positioned(
                            right: 0,
                            bottom: 0,
                            child: IconButton.filled(onPressed: _pickPhoto, icon: const Icon(Icons.camera_alt, size: 18), tooltip: 'Change photo'),
                          ),
                        ]),
                      ),
                      if (_photoPath != null)
                        const Padding(
                          padding: EdgeInsets.only(top: 8),
                          child: Text('New photo selected — save to upload.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white60)),
                        ),
                      const SizedBox(height: 16),
                      ErrorBanner(_error),
                      if (_error != null) const SizedBox(height: 12),
                      _field('full_name', 'Full name'),
                      _field('phone', 'Phone',
                          type: TextInputType.phone,
                          maxLength: 10,
                          validator: (v) => RegExp(r'^\d{10}$').hasMatch(v ?? '') ? null : 'Enter a 10-digit number'),
                      _field('email', 'Email', type: TextInputType.emailAddress),
                      _field('license_number', 'Licence number'),
                      _field('vehicle_info', 'Vehicle (model + number plate)'),
                      FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save profile')),
                    ]),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              // Password + log out (profile fields are edited above).
              const AccountScreen(editProfile: false, embedded: true),
            ]),
    );
  }
}
