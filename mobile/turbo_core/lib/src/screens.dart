import 'dart:async';

import 'package:flutter/material.dart';

import 'auth.dart';
import 'widgets.dart';

/// Root widget for each Turbo app: restores the session, shows login when
/// logged out and [home] when logged in.
class TurboApp extends StatefulWidget {
  const TurboApp({
    super.key,
    required this.role,
    required this.title,
    required this.seed,
    required this.home,
    this.allowRegister = true,
  });

  final String role;
  final String title;
  final Color seed;
  final WidgetBuilder home;
  final bool allowRegister;

  @override
  State<TurboApp> createState() => _TurboAppState();
}

class _TurboAppState extends State<TurboApp> {
  late final AuthController _auth = AuthController(role: widget.role);
  final _navigator = GlobalKey<NavigatorState>();
  int? _lastUserId;

  @override
  void initState() {
    super.initState();
    _auth.addListener(_onAuthChanged);
    _auth.restore();
  }

  void _onAuthChanged() {
    // Logging in or out swaps the root screen; close anything pushed on top of it.
    final id = _auth.user?.id;
    if (id != _lastUserId) {
      _lastUserId = id;
      _navigator.currentState?.popUntil((r) => r.isFirst);
    }
  }

  @override
  void dispose() {
    _auth.removeListener(_onAuthChanged);
    _auth.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AuthScope(
      controller: _auth,
      child: MaterialApp(
        title: widget.title,
        navigatorKey: _navigator,
        debugShowCheckedModeBanner: false,
        theme: turboTheme(widget.seed),
        home: ListenableBuilder(
          listenable: _auth,
          builder: (context, _) {
            if (!_auth.ready) return const Scaffold(body: Center(child: CircularProgressIndicator()));
            if (_auth.user == null) return LoginScreen(title: widget.title, allowRegister: widget.allowRegister);
            return widget.home(context);
          },
        ),
      ),
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.title, this.allowRegister = true});

  final String title;
  final bool allowRegister;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _hide = true;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final auth = AuthScope.read(context);
      final challenge = await auth.login(_email.text, _password.text);
      if (challenge != null && mounted) {
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => EmailCodeScreen(challenge: challenge)));
      }
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _form,
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Icon(Icons.local_taxi, size: 56, color: scheme.primary),
                  const SizedBox(height: 12),
                  Text(widget.title, textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineMedium),
                  const SizedBox(height: 4),
                  const Text('Log in to continue', textAlign: TextAlign.center, style: TextStyle(color: Colors.white60)),
                  const SizedBox(height: 28),
                  ErrorBanner(_error),
                  if (_error != null) const SizedBox(height: 12),
                  TextFormField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    decoration: const InputDecoration(labelText: 'Email', prefixIcon: Icon(Icons.mail_outline)),
                    validator: (v) => (v == null || !v.contains('@')) ? 'Enter your email' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _password,
                    obscureText: _hide,
                    autofillHints: const [AutofillHints.password],
                    onFieldSubmitted: (_) => _submit(),
                    decoration: InputDecoration(
                      labelText: 'Password',
                      prefixIcon: const Icon(Icons.lock_outline),
                      suffixIcon: IconButton(
                        icon: Icon(_hide ? Icons.visibility : Icons.visibility_off),
                        onPressed: () => setState(() => _hide = !_hide),
                      ),
                    ),
                    validator: (v) => (v == null || v.isEmpty) ? 'Enter your password' : null,
                  ),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _busy ? null : _submit,
                    style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
                    child: Text(_busy ? 'Signing in…' : 'Sign in'),
                  ),
                  if (widget.allowRegister) ...[
                    const SizedBox(height: 12),
                    TextButton(
                      onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const RegisterScreen())),
                      child: const Text("New here? Create an account"),
                    ),
                  ],
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _form = GlobalKey<FormState>();
  final _c = {
    for (final k in ['full_name', 'username', 'email', 'phone', 'password', 'password2']) k: TextEditingController(),
  };
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    for (final c in _c.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final auth = AuthScope.read(context);
      final challenge = await auth.register({
        for (final k in ['full_name', 'username', 'email', 'phone', 'password']) k: _c[k]!.text.trim(),
      });
      if (challenge != null && mounted) {
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => EmailCodeScreen(challenge: challenge)));
      }
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _field(String key, String label,
      {TextInputType? type, bool obscure = false, String? Function(String?)? validator, int? maxLength}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: _c[key],
        keyboardType: type,
        obscureText: obscure,
        maxLength: maxLength,
        decoration: InputDecoration(labelText: label, counterText: ''),
        validator: validator ?? ((v) => (v == null || v.trim().isEmpty) ? 'Required' : null),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final role = AuthScope.read(context).role;
    return Scaffold(
      appBar: AppBar(title: Text('Create ${role == 'driver' ? 'driver' : 'rider'} account')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _form,
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              ErrorBanner(_error),
              if (_error != null) const SizedBox(height: 12),
              _field('full_name', 'Full name'),
              _field('username', 'Username'),
              _field('email', 'Email',
                  type: TextInputType.emailAddress,
                  validator: (v) => (v == null || !v.contains('@')) ? 'Enter a valid email' : null),
              _field('phone', 'Phone (10 digits)',
                  type: TextInputType.phone,
                  maxLength: 10,
                  validator: (v) => RegExp(r'^\d{10}$').hasMatch(v ?? '') ? null : 'Enter a 10-digit number'),
              _field('password', 'Password',
                  obscure: true, validator: (v) => (v ?? '').length < 8 ? 'At least 8 characters' : null),
              _field('password2', 'Repeat password',
                  obscure: true, validator: (v) => v != _c['password']!.text ? 'Passwords do not match' : null),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: _busy ? null : _submit,
                style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
                child: Text(_busy ? 'Creating account…' : 'Create account'),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

/// Profile + password + log out. Apps can add extra cards with [extra].
/// Set [embedded] when placing it inside another scrolling page.
class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key, this.extra = const [], this.editProfile = true, this.embedded = false});

  final List<Widget> extra;
  final bool editProfile;
  final bool embedded;

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  late final _name = TextEditingController();
  late final _email = TextEditingController();
  late final _phone = TextEditingController();
  bool _busy = false;
  bool _filled = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final user = AuthScope.of(context).user;
    if (!_filled && user != null) {
      _name.text = user.fullName;
      _email.text = user.email;
      _phone.text = user.phone;
      _filled = true;
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      await AuthScope.read(context)
          .updateProfile({'full_name': _name.text.trim(), 'email': _email.text.trim(), 'phone': _phone.text.trim()});
      if (mounted) showSnack(context, 'Profile saved.');
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = AuthScope.of(context);
    return ListView(
        shrinkWrap: widget.embedded,
        physics: widget.embedded ? const NeverScrollableScrollPhysics() : null,
        padding: widget.embedded ? EdgeInsets.zero : const EdgeInsets.all(16),
        children: [
      if (widget.editProfile)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text('Profile', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              TextField(controller: _name, decoration: const InputDecoration(labelText: 'Full name')),
              const SizedBox(height: 10),
              TextField(controller: _email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email')),
              const SizedBox(height: 10),
              TextField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                maxLength: 10,
                decoration: const InputDecoration(labelText: 'Phone', counterText: ''),
              ),
              const SizedBox(height: 12),
              FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save profile')),
            ]),
          ),
        ),
      if (widget.editProfile) const SizedBox(height: 12),
      const ChangePasswordCard(),
      for (final w in widget.extra) ...[const SizedBox(height: 12), w],
      const SizedBox(height: 12),
      OutlinedButton.icon(
        onPressed: () async {
          if (await confirmDialog(context, 'Log out?', 'You will need to sign in again.', action: 'Log out')) {
            await auth.logout();
          }
        },
        icon: const Icon(Icons.logout),
        label: Text('Log out ${auth.user?.email ?? ''}'),
      ),
    ]);
  }
}

class ChangePasswordCard extends StatefulWidget {
  const ChangePasswordCard({super.key});

  @override
  State<ChangePasswordCard> createState() => _ChangePasswordCardState();
}

class _ChangePasswordCardState extends State<ChangePasswordCard> {
  final _old = TextEditingController();
  final _new = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _old.dispose();
    _new.dispose();
    super.dispose();
  }

  Future<void> _change() async {
    if (_old.text.isEmpty || _new.text.isEmpty) return;
    setState(() => _busy = true);
    try {
      await AuthScope.read(context)
          .api
          .post('/auth/change-password/', {'old_password': _old.text, 'new_password': _new.text});
      _old.clear();
      _new.clear();
      if (mounted) showSnack(context, 'Password changed.');
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
            Text('Change password', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(controller: _old, obscureText: true, decoration: const InputDecoration(labelText: 'Current password')),
            const SizedBox(height: 10),
            TextField(controller: _new, obscureText: true, decoration: const InputDecoration(labelText: 'New password')),
            const SizedBox(height: 12),
            FilledButton.tonal(onPressed: _busy ? null : _change, child: Text(_busy ? 'Changing…' : 'Change password')),
          ]),
        ),
      );
}


/// "Check your email": enter the 6-digit code to finish login or registration.
class EmailCodeScreen extends StatefulWidget {
  const EmailCodeScreen({super.key, required this.challenge});

  final EmailChallenge challenge;

  @override
  State<EmailCodeScreen> createState() => _EmailCodeScreenState();
}

class _EmailCodeScreenState extends State<EmailCodeScreen> {
  final _code = TextEditingController();
  String? _error;
  String? _info;
  bool _busy = false;
  int _wait = 60;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startCooldown();
  }

  void _startCooldown() {
    _timer?.cancel();
    _wait = 60;
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      setState(() => _wait = _wait > 0 ? _wait - 1 : 0);
      if (_wait == 0) t.cancel();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _code.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    if (!RegExp(r'^\d{6}$').hasMatch(_code.text)) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthScope.read(context).verifyEmail(widget.challenge, _code.text);
      // TurboApp swaps to the home screen once the user is set.
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resend() async {
    setState(() => _busy = true);
    try {
      final msg = await AuthScope.read(context).resendCode(widget.challenge);
      if (mounted) setState(() => _info = msg);
      _startCooldown();
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final register = widget.challenge.purpose == 'register';
    return Scaffold(
      appBar: AppBar(title: Text(register ? 'Verify your email' : 'Check your email')),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(24), children: [
          Icon(Icons.mark_email_read_outlined, size: 56, color: Theme.of(context).colorScheme.primary),
          const SizedBox(height: 16),
          Text('We sent a 6-digit code to ${widget.challenge.maskedEmail}.',
              textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(register ? 'Enter it to activate your account.' : 'Enter it to finish logging in.',
              textAlign: TextAlign.center, style: const TextStyle(color: Colors.white60)),
          const SizedBox(height: 20),
          ErrorBanner(_error),
          if (_info != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_info!, textAlign: TextAlign.center)),
          const SizedBox(height: 12),
          TextField(
            controller: _code,
            autofocus: true,
            keyboardType: TextInputType.number,
            maxLength: 6,
            textAlign: TextAlign.center,
            autofillHints: const [AutofillHints.oneTimeCode],
            style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w800, letterSpacing: 12),
            decoration: const InputDecoration(counterText: '', hintText: '••••••'),
            onChanged: (v) {
              if (v.length == 6) _verify();
            },
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _busy ? null : _verify, child: Text(_busy ? 'Checking…' : 'Verify')),
          TextButton(
            onPressed: _busy || _wait > 0 ? null : _resend,
            child: Text(_wait > 0 ? 'Resend code in ${_wait}s' : 'Resend code'),
          ),
          const Text('The code expires in 10 minutes. Check your spam folder if you can\'t find it.',
              textAlign: TextAlign.center, style: TextStyle(color: Colors.white38, fontSize: 12)),
        ]),
      ),
    );
  }
}
