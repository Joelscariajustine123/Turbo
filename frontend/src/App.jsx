import { Navigate, Route, Routes } from 'react-router-dom';
import { RoleLayout } from './components/Layout';
import Account from './pages/Account';
import { AdminAccount, Drivers, Messages, Overview, Reports, Riders, Rides as AdminRides } from './pages/admin/Admin';
import { Dashboard, Earnings, History, Profile } from './pages/driver/Driver';
import { Contact, Landing, Login, Register } from './pages/Public';
import Book from './pages/rider/Book';
import { RideDetail, RideList } from './pages/rider/Rides';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login/:role" element={<Login />} />
      <Route path="/register/:role" element={<Register />} />
      <Route path="/contact" element={<Contact />} />

      <Route path="/rider" element={<RoleLayout role="rider" />}>
        <Route index element={<Book />} />
        <Route path="rides" element={<RideList />} />
        <Route path="rides/:id" element={<RideDetail />} />
        <Route path="account" element={<Account />} />
      </Route>

      <Route path="/driver" element={<RoleLayout role="driver" />}>
        <Route index element={<Dashboard />} />
        <Route path="earnings" element={<Earnings />} />
        <Route path="history" element={<History />} />
        <Route path="profile" element={<Profile />} />
      </Route>

      <Route path="/admin" element={<RoleLayout role="admin" />}>
        <Route index element={<Overview />} />
        <Route path="rides" element={<AdminRides />} />
        <Route path="payments" element={<AdminRides payments />} />
        <Route path="reports" element={<Reports />} />
        <Route path="riders" element={<Riders />} />
        <Route path="drivers" element={<Drivers />} />
        <Route path="messages" element={<Messages />} />
        <Route path="account" element={<AdminAccount />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
