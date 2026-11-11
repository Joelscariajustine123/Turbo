import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Where the Django server is. Override at build/run time with
///   flutter run --dart-define=API_URL=http://192.168.1.20:8000
/// The default reaches the host machine from the Android emulator.
class TurboConfig {
  static const apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000');
}

class ApiException implements Exception {
  ApiException(this.message, [this.status = 0]);

  final String message;
  final int status;

  @override
  String toString() => message;
}

/// Talks to /api on the Turbo server: adds the JWT, refreshes it once on 401,
/// and turns error responses into [ApiException] with a readable message.
class ApiClient {
  ApiClient({String? baseUrl, http.Client? client})
      : baseUrl = (baseUrl ?? TurboConfig.apiUrl).replaceAll(RegExp(r'/+$'), ''),
        _http = client ?? http.Client();

  final String baseUrl;
  final http.Client _http;
  String? _access;
  String? _refresh;
  Future<bool>? _refreshing;

  /// Called when the refresh token is no longer valid (the user must log in again).
  void Function()? onSessionExpired;

  static const _kAccess = 'turbo.access';
  static const _kRefresh = 'turbo.refresh';
  static const _kUser = 'turbo.user';
  static const _timeout = Duration(seconds: 20);

  bool get hasSession => _refresh != null;

  /// Loads a saved session. Returns the saved user JSON, if any.
  Future<Map<String, dynamic>?> restore() async {
    final prefs = await SharedPreferences.getInstance();
    _access = prefs.getString(_kAccess);
    _refresh = prefs.getString(_kRefresh);
    final user = prefs.getString(_kUser);
    if (_refresh == null || user == null) return null;
    try {
      return jsonDecode(user) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  /// Stores tokens (+ user) from a login / register response.
  Future<void> saveSession(Map<String, dynamic> data) async {
    _access = data['access'] as String?;
    _refresh = data['refresh'] as String?;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kAccess, _access ?? '');
    await prefs.setString(_kRefresh, _refresh ?? '');
    if (data['user'] != null) await prefs.setString(_kUser, jsonEncode(data['user']));
  }

  Future<void> saveUser(Map<String, dynamic> user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kUser, jsonEncode(user));
  }

  Future<void> clearSession() async {
    _access = null;
    _refresh = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kAccess);
    await prefs.remove(_kRefresh);
    await prefs.remove(_kUser);
  }

  String? get refreshToken => _refresh;

  Uri uri(String path, [Map<String, String>? query]) {
    final u = Uri.parse('$baseUrl/api$path');
    final q = {...?query}..removeWhere((_, v) => v.isEmpty);
    return q.isEmpty ? u : u.replace(queryParameters: q);
  }

  Future<dynamic> get(String path, {Map<String, String>? query}) => _send('GET', path, query: query);

  Future<dynamic> post(String path, [Object? body]) => _send('POST', path, body: body);

  Future<dynamic> patch(String path, Object body) => _send('PATCH', path, body: body);

  Future<dynamic> delete(String path) => _send('DELETE', path);

  /// POST without a token (login, register, contact).
  Future<dynamic> postPublic(String path, Object body) => _send('POST', path, body: body, auth: false);

  /// Multipart request, e.g. uploading a profile photo.
  Future<dynamic> multipart(String method, String path, Map<String, String> fields,
      {String? fileField, String? filePath}) {
    Future<http.BaseRequest> build() async {
      final req = http.MultipartRequest(method, uri(path))..fields.addAll(fields);
      if (fileField != null && filePath != null) {
        req.files.add(await http.MultipartFile.fromPath(fileField, filePath));
      }
      return req;
    }

    return _execute(build, auth: true, retry: true);
  }

  Future<dynamic> _send(String method, String path,
      {Object? body, Map<String, String>? query, bool auth = true}) {
    Future<http.BaseRequest> build() async {
      final req = http.Request(method, uri(path, query));
      if (body != null) {
        req.headers['Content-Type'] = 'application/json';
        req.body = jsonEncode(body);
      }
      return req;
    }

    return _execute(build, auth: auth, retry: true);
  }

  Future<dynamic> _execute(Future<http.BaseRequest> Function() build,
      {required bool auth, required bool retry}) async {
    final req = await build();
    req.headers['Accept'] = 'application/json';
    if (auth && _access != null && _access!.isNotEmpty) {
      req.headers['Authorization'] = 'Bearer $_access';
    }

    http.Response res;
    try {
      res = await http.Response.fromStream(await _http.send(req).timeout(_timeout));
    } on TimeoutException {
      throw ApiException('The server took too long to respond.');
    } catch (_) {
      throw ApiException("Can't reach the server at $baseUrl. Check your connection.");
    }

    if (res.statusCode == 401 && auth && retry && _refresh != null && _refresh!.isNotEmpty) {
      if (await _refreshAccess()) return _execute(build, auth: auth, retry: false);
      await clearSession();
      onSessionExpired?.call();
      throw ApiException('Your session has expired. Please log in again.', 401);
    }
    return _decode(res);
  }

  Future<bool> _refreshAccess() {
    return _refreshing ??= () async {
      try {
        final res = await _http
            .post(uri('/auth/refresh/'),
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: jsonEncode({'refresh': _refresh}))
            .timeout(_timeout);
        if (res.statusCode != 200) return false;
        final data = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
        await saveSession({'access': data['access'], 'refresh': data['refresh'] ?? _refresh});
        return true;
      } catch (_) {
        return false;
      } finally {
        _refreshing = null;
      }
    }();
  }

  dynamic _decode(http.Response res) {
    final text = utf8.decode(res.bodyBytes);
    dynamic data;
    if (text.isNotEmpty) {
      try {
        data = jsonDecode(text);
      } catch (_) {
        data = null;
      }
    }
    if (res.statusCode >= 200 && res.statusCode < 300) return data;
    final message = (data is Map && data['detail'] is String)
        ? data['detail'] as String
        : 'Request failed (${res.statusCode}).';
    throw ApiException(message, res.statusCode);
  }
}
