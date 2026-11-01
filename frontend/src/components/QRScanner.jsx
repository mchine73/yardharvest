import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

export default function QRScanner({ isOpen, onScan, onClose }) {
  const { t } = useTranslation();
  const scannerRef = useRef(null);
  const html5QrRef = useRef(null);
  // Holds a catalog KEY, translated at render, so the camera effect below
  // can keep depending on [isOpen] alone.
  const [error, setError] = useState('');
  const [scanning, setScanning] = useState(false);

  // Keep the latest onScan in a ref so the camera effect depends only on
  // [isOpen]. Parents pass a new inline onScan each render; depending on it
  // would tear down and restart the camera mid-scan (flicker, dropped scans).
  const onScanRef = useRef(onScan);
  useEffect(() => { onScanRef.current = onScan; });

  useEffect(() => {
    if (!isOpen) return;

    let mounted = true;

    const startScanner = async () => {
      try {
        const { Html5Qrcode } = await import('html5-qrcode');
        if (!mounted) return;

        const scanner = new Html5Qrcode('qr-scanner-region');
        html5QrRef.current = scanner;
        setScanning(true);
        setError('');

        await scanner.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 250, height: 250 } },
          (decodedText) => {
            // Parse the QR URL: /gardens/{id}/resources/{resId}/scan
            const match = decodedText.match(/\/gardens\/(\d+)\/resources\/(\d+)\/scan/);
            if (match) {
              onScanRef.current(parseInt(match[1]), parseInt(match[2]));
            } else {
              setError('qr.errUnrecognized');
            }
          },
          () => {} // ignore scan failures (continuous scanning)
        );
      } catch (err) {
        if (mounted) {
          if (err.toString().includes('NotAllowed') || err.toString().includes('Permission')) {
            setError('qr.errPermission');
          } else {
            setError('qr.errCamera');
          }
          setScanning(false);
        }
      }
    };

    startScanner();

    return () => {
      mounted = false;
      const scanner = html5QrRef.current;
      html5QrRef.current = null;
      if (scanner) {
        // clear() must run only AFTER stop() resolves, or html5-qrcode throws
        // "Cannot clear while scan is ongoing".
        scanner.stop().then(() => scanner.clear()).catch(() => {});
      }
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal d-block" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }} onClick={onClose}>
      <div className="modal-dialog modal-dialog-centered" onClick={e => e.stopPropagation()}>
        <div className="modal-content" style={{ borderRadius: 12 }}>
          <div className="modal-header border-0 pb-0">
            <h5 className="modal-title"><i className="bi bi-qr-code-scan me-2"></i>{t('qr.title')}</h5>
            <button type="button" className="btn-close" onClick={onClose}></button>
          </div>
          <div className="modal-body text-center">
            {error && (
              <div className="alert alert-warning py-2 small">
                <i className="bi bi-exclamation-triangle me-1"></i>{t(error)}
              </div>
            )}
            <div id="qr-scanner-region" ref={scannerRef} style={{ width: '100%' }}></div>
            {!scanning && !error && (
              <div className="py-4">
                <div className="spinner-border text-success"></div>
                <p className="text-muted mt-2">{t('qr.starting')}</p>
              </div>
            )}
            <p className="text-muted small mt-2">{t('qr.pointCamera')}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
