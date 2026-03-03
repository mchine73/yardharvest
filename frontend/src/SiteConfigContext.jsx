import { createContext, useContext, useState, useEffect } from 'react';
import { adminAPI } from './api';

const SiteConfigContext = createContext({ marketplaceEnabled: false });

export function SiteConfigProvider({ children }) {
  const [config, setConfig] = useState({ marketplaceEnabled: false });
  const [loading, setLoading] = useState(true);

  const refreshConfig = () => {
    adminAPI.siteConfig().then(res => {
      setConfig({ marketplaceEnabled: res.data.marketplace_enabled ?? false });
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { refreshConfig(); }, []);

  return (
    <SiteConfigContext.Provider value={{ ...config, loading, refreshConfig }}>
      {children}
    </SiteConfigContext.Provider>
  );
}

export function useSiteConfig() {
  return useContext(SiteConfigContext);
}
