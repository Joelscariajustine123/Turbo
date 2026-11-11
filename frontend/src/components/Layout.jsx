import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom';
import { homeFor, useAuth } from '../auth/AuthContext';

const NAV = {
  rider: [
    ['/rider', 'Book a ride', true],
    ['/rider/rides', 'My rides'],
    ['/rider/account', 'Account'],
  ],
  driver: [
    ['/driver', 'Dashboard', true],
    ['/driver/earnings', 'Earnings'],
    ['/driver/history', 'History'],
    ['/driver/profile', 'Profile'],
  ],
  admin: [
    ['/admin', 'Overview', true],
    ['/admin/rides', 'Rides'],
    ['/admin/payments', 'Payments'],
    ['/admin/reports', 'Reports'],
    ['/admin/riders', 'Riders'],
    ['/admin/drivers', 'Drivers'],
    ['/admin/messages', 'Messages'],
    ['/admin/account', 'Account'],
  ],
};

/** Guards a section of the app to one role and renders its navigation. */
export function RoleLayout({ role }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  if (!user) return <Navigate to={`/login/${role}`} replace state={{ from: location.pathname }} />;
  if (user.role !== role) return <Navigate to={homeFor(user.role)} replace />;

  return (
    <div className={`shell shell-${role}`}>
      <header className="topbar">
        <NavLink to={homeFor(role)} className="brand">
          Turbo<span>{role === 'admin' ? ' Admin' : role === 'driver' ? ' Driver' : ''}</span>
        </NavLink>
        <nav className="nav">
          {NAV[role].map(([to, label, end]) => (
            <NavLink key={to} to={to} end={end}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="who">
          <span className="muted">{user.full_name}</span>
          <button className="btn ghost small" onClick={logout}>
            Log out
          </button>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </div>
  );
}
