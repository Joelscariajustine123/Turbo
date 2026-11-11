double toDouble(dynamic v) {
  if (v == null) return 0;
  if (v is num) return v.toDouble();
  return double.tryParse(v.toString()) ?? 0;
}

double? toDoubleOrNull(dynamic v) => v == null ? null : toDouble(v);

DateTime? toDate(dynamic v) => v == null ? null : DateTime.tryParse(v.toString())?.toLocal();

String str(dynamic v) => v?.toString() ?? '';

class User {
  User({
    required this.id,
    required this.username,
    required this.email,
    required this.fullName,
    required this.phone,
    required this.role,
    required this.isActive,
    this.dateJoined,
  });

  factory User.fromJson(Map<String, dynamic> j) => User(
        id: j['id'] as int,
        username: str(j['username']),
        email: str(j['email']),
        fullName: str(j['full_name']),
        phone: str(j['phone']),
        role: str(j['role']),
        isActive: j['is_active'] != false,
        dateJoined: toDate(j['date_joined']),
      );

  final int id;
  final String username;
  final String email;
  final String fullName;
  final String phone;
  final String role;
  final bool isActive;
  final DateTime? dateJoined;

  Map<String, dynamic> toJson() => {
        'id': id,
        'username': username,
        'email': email,
        'full_name': fullName,
        'phone': phone,
        'role': role,
        'is_active': isActive,
        'date_joined': dateJoined?.toUtc().toIso8601String(),
      };
}

class RidePerson {
  RidePerson({required this.id, required this.fullName, this.phone, this.vehicleInfo, this.vehicleNumber, this.vehicleType, this.photo});

  factory RidePerson.fromJson(Map<String, dynamic> j) => RidePerson(
        id: j['id'] as int,
        fullName: str(j['full_name']),
        phone: j['phone'] as String?,
        vehicleInfo: j['vehicle_info'] as String?,
        vehicleNumber: j['vehicle_number'] as String?,
        vehicleType: j['vehicle_type'] as String?,
        photo: j['profile_photo'] as String?,
      );

  final int id;
  final String fullName;
  final String? phone;
  final String? vehicleInfo;
  final String? vehicleNumber;
  final String? vehicleType;
  final String? photo;
}

class Ride {
  Ride({
    required this.id,
    required this.pickup,
    required this.drop,
    required this.carType,
    required this.carTypeDisplay,
    required this.distance,
    required this.fare,
    required this.status,
    required this.statusDisplay,
    required this.rider,
    required this.canCancel,
    this.otpVerified = false,
    this.paymentStatus = 'UNPAID',
    this.needsPayment = false,
    this.pickupLat,
    this.pickupLng,
    this.dropLat,
    this.dropLng,
    this.paymentMethod,
    this.paymentMethodDisplay,
    this.transactionId,
    this.createdAt,
    this.driver,
    this.rating,
  });

  factory Ride.fromJson(Map<String, dynamic> j) => Ride(
        id: j['id'] as int,
        pickup: str(j['pickup_location']),
        drop: str(j['drop_location']),
        pickupLat: toDoubleOrNull(j['pickup_lat']),
        pickupLng: toDoubleOrNull(j['pickup_lng']),
        dropLat: toDoubleOrNull(j['drop_lat']),
        dropLng: toDoubleOrNull(j['drop_lng']),
        carType: str(j['car_type']),
        carTypeDisplay: str(j['car_type_display']),
        distance: toDouble(j['distance']),
        fare: toDouble(j['fare']),
        status: str(j['status']),
        statusDisplay: str(j['status_display']),
        paymentMethod: j['payment_method'] as String?,
        paymentMethodDisplay: j['payment_method_display'] as String?,
        transactionId: j['transaction_id'] as String?,
        createdAt: toDate(j['created_at']),
        rider: RidePerson.fromJson(j['rider'] as Map<String, dynamic>),
        driver: j['driver'] == null ? null : RidePerson.fromJson(j['driver'] as Map<String, dynamic>),
        rating: toDoubleOrNull(j['rating']),
        canCancel: j['can_cancel'] == true,
        otpVerified: j['otp_verified'] == true,
        paymentStatus: (j['payment_status'] as String?) ?? 'UNPAID',
        needsPayment: j['needs_payment'] == true,
      );

  final int id;
  final String pickup;
  final String drop;
  final double? pickupLat;
  final double? pickupLng;
  final double? dropLat;
  final double? dropLng;
  final String carType;
  final String carTypeDisplay;
  final double distance;
  final double fare;
  final String status;
  final String statusDisplay;
  final String? paymentMethod;
  final String? paymentMethodDisplay;
  final String? transactionId;
  final DateTime? createdAt;
  final RidePerson rider;
  final RidePerson? driver;
  final double? rating;
  final bool canCancel;
  final bool otpVerified;
  final String paymentStatus; // UNPAID | CASH_DUE | PAID
  final bool needsPayment;

  bool get isActive => const ['PENDING', 'CONFIRMED', 'ACCEPTED', 'ARRIVED', 'IN_PROGRESS'].contains(status);

  /// Driver assigned and the trip is under way (live location is shared).
  bool get isTrip => const ['ACCEPTED', 'ARRIVED', 'IN_PROGRESS'].contains(status);
}

class DriverProfile {
  DriverProfile({
    required this.id,
    required this.fullName,
    required this.email,
    required this.phone,
    required this.licenseNumber,
    required this.vehicleInfo,
    this.vehicleNumber = '',
    this.vehicleType = '',
    required this.availability,
    required this.availabilityDisplay,
    required this.isActive,
    this.photo,
  });

  factory DriverProfile.fromJson(Map<String, dynamic> j) => DriverProfile(
        id: j['id'] as int,
        fullName: str(j['full_name']),
        email: str(j['email']),
        phone: str(j['phone']),
        licenseNumber: str(j['license_number']),
        vehicleInfo: str(j['vehicle_info']),
        vehicleNumber: str(j['vehicle_number']),
        vehicleType: str(j['vehicle_type']),
        availability: str(j['availability_status']),
        availabilityDisplay: str(j['availability_display']),
        isActive: j['is_active'] != false,
        photo: j['profile_photo'] as String?,
      );

  final int id;
  final String fullName;
  final String email;
  final String phone;
  final String licenseNumber;
  final String vehicleInfo;
  final String vehicleNumber;
  final String vehicleType;
  final String availability;
  final String availabilityDisplay;
  final bool isActive;
  final String? photo;
}

class Choice {
  Choice(this.value, this.label, [this.rate = 0]);

  final String value;
  final String label;
  final double rate;
}

/// Static data from GET /api/meta/.
class Meta {
  Meta({
    required this.baseFare,
    required this.carTypes,
    required this.rideStatuses,
    required this.availability,
    required this.upiId,
  });

  factory Meta.fromJson(Map<String, dynamic> j) {
    List<Choice> list(String key) => (j[key] as List)
        .map((e) => Choice(str(e['value']), str(e['label']), toDouble(e['rate_per_km'])))
        .toList();
    return Meta(
      baseFare: toDouble(j['base_fare']),
      carTypes: list('car_types'),
      rideStatuses: list('ride_statuses'),
      availability: list('availability_statuses'),
      upiId: str(j['upi_id']),
    );
  }

  final double baseFare;
  final List<Choice> carTypes;
  final List<Choice> rideStatuses;
  final List<Choice> availability;
  final String upiId;
}

/// One page of a paginated list endpoint.
class PageOf<T> {
  PageOf({required this.count, required this.hasNext, required this.results});

  factory PageOf.fromJson(dynamic json, T Function(Map<String, dynamic>) parse) {
    final j = json as Map<String, dynamic>;
    return PageOf(
      count: j['count'] as int? ?? 0,
      hasNext: j['next'] != null,
      results: (j['results'] as List).map((e) => parse(e as Map<String, dynamic>)).toList(),
    );
  }

  final int count;
  final bool hasNext;
  final List<T> results;
}
