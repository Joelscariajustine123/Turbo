import 'package:flutter/widgets.dart';

import 'api_client.dart';
import 'models.dart';

/// Holds the logged-in user for one app. Each app is locked to one [role].
class AuthController extends ChangeNotifier {
  AuthController({required this.role, ApiClient? api}) : api = api ?? ApiClient() {
    this.api.onSessionExpired = () {
      _user = null;
      notifyListeners();
    };
  }

  final String role;
  final ApiClient api;
  User? _user;
  bool _ready = false;
  Meta? _meta;

  User? get user => _user;
  bool get ready => _ready;

  Future<void> restore() async {
    final saved = await api.restore();
    if (saved != null && saved['role'] == role) {
      _user = User.fromJson(saved);
    } else if (saved != null) {
      await api.clearSession();
    }
    _ready = true;
    notifyListeners();
    if (_user != null) {
      // Refresh the profile in the background; a dead session logs out via onSessionExpired.
      try {
        await _setUser(User.fromJson(await api.get('/auth/me/') as Map<String, dynamic>));
      } catch (_) {}
    }
  }

  /// Returns an [EmailChallenge] when a code was emailed (the usual case), or null when logged in.
  Future<EmailChallenge?> login(String email, String password) async {
    final data = await api.postPublic('/auth/login/', {'email': email.trim(), 'password': password, 'role': role})
        as Map<String, dynamic>;
    return _handle(data);
  }

  Future<EmailChallenge?> register(Map<String, String> fields) async {
    final data = await api.postPublic('/auth/register/', {...fields, 'role': role}) as Map<String, dynamic>;
    return _handle(data);
  }

  /// Finish login/registration with the 6-digit code from the email.
  Future<void> verifyEmail(EmailChallenge challenge, String code) async {
    final data = await api.postPublic('/auth/verify-email/', {'challenge': challenge.token, 'code': code})
        as Map<String, dynamic>;
    await _handle(data);
  }

  Future<String> resendCode(EmailChallenge challenge) async {
    final data = await api.postPublic('/auth/resend-code/', {'challenge': challenge.token}) as Map<String, dynamic>;
    return str(data['detail']);
  }

  Future<EmailChallenge?> _handle(Map<String, dynamic> data) async {
    if (data['otp_required'] == true) {
      return EmailChallenge(str(data['challenge']), str(data['email']), str(data['purpose']));
    }
    await api.saveSession(data);
    _user = User.fromJson(data['user'] as Map<String, dynamic>);
    notifyListeners();
    return null;
  }

  Future<void> logout() async {
    final refresh = api.refreshToken;
    if (refresh != null && refresh.isNotEmpty) {
      try {
        await api.post('/auth/logout/', {'refresh': refresh});
      } catch (_) {}
    }
    await api.clearSession();
    _user = null;
    notifyListeners();
  }

  Future<void> updateProfile(Map<String, String> fields) async {
    await _setUser(User.fromJson(await api.patch('/auth/me/', fields) as Map<String, dynamic>));
  }

  Future<void> _setUser(User user) async {
    _user = user;
    await api.saveUser(user.toJson());
    notifyListeners();
  }

  /// Reloads the user after another screen changed it (e.g. the driver profile).
  Future<void> reloadUser() async {
    await _setUser(User.fromJson(await api.get('/auth/me/') as Map<String, dynamic>));
  }

  /// Cached GET /api/meta/.
  Future<Meta> meta() async => _meta ??= Meta.fromJson(await api.get('/meta/') as Map<String, dynamic>);
}

/// Makes the [AuthController] available to every screen: `AuthScope.of(context)`.
class AuthScope extends InheritedNotifier<AuthController> {
  const AuthScope({super.key, required AuthController controller, required super.child})
      : super(notifier: controller);

  static AuthController of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AuthScope>()!.notifier!;

  /// Same as [of] but without rebuilding when the user changes (for callbacks).
  static AuthController read(BuildContext context) =>
      context.getInheritedWidgetOfExactType<AuthScope>()!.notifier!;
}


/// A pending login/registration waiting for the emailed code.
class EmailChallenge {
  EmailChallenge(this.token, this.maskedEmail, this.purpose);

  final String token;
  final String maskedEmail;
  final String purpose; // 'login' | 'register'
}
