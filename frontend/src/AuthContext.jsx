import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI, cartAPI, messagesAPI, notificationsAPI } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cartCount, setCartCount] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifCount, setNotifCount] = useState(0);

  const fetchUser = async () => {
    try {
      const res = await authAPI.me();
      setUser(res.data);
      if (res.data) {
        refreshCounts();
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const refreshCounts = async () => {
    try {
      const [cart, msgs, notifs] = await Promise.all([
        cartAPI.count(),
        messagesAPI.unreadCount(),
        notificationsAPI.unreadCount(),
      ]);
      setCartCount(cart.data.count);
      setUnreadCount(msgs.data.count);
      setNotifCount(notifs.data.unread_count);
    } catch {
      // ignore if not logged in
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  // Poll for notification count every 30s when logged in
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(async () => {
      try {
        const res = await notificationsAPI.unreadCount();
        setNotifCount(res.data.unread_count);
      } catch { /* ignore */ }
    }, 30000);
    return () => clearInterval(interval);
  }, [user]);

  const login = async (email, password) => {
    const res = await authAPI.login(email, password);
    setUser(res.data);
    refreshCounts();
    return res.data;
  };

  const register = async (data) => {
    const res = await authAPI.register(data);
    setUser(res.data);
    refreshCounts();
    return res.data;
  };

  const logout = async () => {
    await authAPI.logout();
    setUser(null);
    setCartCount(0);
    setUnreadCount(0);
    setNotifCount(0);
  };

  return (
    <AuthContext.Provider value={{
      user, loading, login, register, logout, fetchUser,
      cartCount, setCartCount, unreadCount, setUnreadCount,
      notifCount, setNotifCount, refreshCounts,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
