import { createContext, useContext, useState, useEffect } from 'react';
import { adminAPI } from './api';

const SiteConfigContext = createContext({ marketplaceEnabled: false, languages: ['en'] });

export function SiteConfigProvider({ children }) {
  const [config, setConfig] = useState({ marketplaceEnabled: false, languages: ['en'] });
  const [loading, setLoading] = useState(true);

  const refreshConfig = () => {
    adminAPI.siteConfig().then(res => {
      setConfig({
        marketplaceEnabled: res.data.marketplace_enabled ?? false,
        // Default to English-only: if the call fails we must not offer a
        // language we cannot actually render.
        languages: res.data.languages ?? ['en'],
      });
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
