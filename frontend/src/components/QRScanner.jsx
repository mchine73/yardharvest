import { useEffect, useRef, useState } from 'react';

export default function QRScanner({ isOpen, onScan, onClose }) {
  const scannerRef = useRef(null);
  const html5QrRef = useRef(null);
  const [error, setError] = useState('');
  const [scanning, setScanning] = useState(false);

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
              onScan(parseInt(match[1]), parseInt(match[2]));
            } else {
              setError('Unrecognized QR code. Please scan a YardHarvest resource QR code.');
            }
          },
          () => {} // ignore scan failures (continuous scanning)
        );
      } catch (err) {
        if (mounted) {
          if (err.toString().includes('NotAllowed') || err.toString().includes('Permission')) {
            setError('Camera permission denied. Please allow camera access and try again.');
          } else {
            setError('Unable to start camera. Please try again or use your phone\'s built-in camera to scan.');
          }
          setScanning(false);
        }
      }
    };

    startScanner();

    return () => {
      mounted = false;
      if (html5QrRef.current) {
        html5QrRef.current.stop().catch(() => {});
        html5QrRef.current.clear();
        html5QrRef.current = null;
      }
    };
  }, [isOpen, onScan]);

  if (!isOpen) return null;

  return (
    <div className="modal d-block" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }} onClick={onClose}>
      <div className="modal-dialog modal-dialog-centered" onClick={e => e.stopPropagation()}>
        <div className="modal-content" style={{ borderRadius: 12 }}>
          <div className="modal-header border-0 pb-0">
            <h5 className="modal-title"><i className="bi bi-qr-code-scan me-2"></i>Scan Resource QR Code</h5>
            <button type="button" className="btn-close" onClick={onClose}></button>
          </div>
          <div className="modal-body text-center">
            {error && (
              <div className="alert alert-warning py-2 small">
                <i className="bi bi-exclamation-triangle me-1"></i>{error}
              </div>
            )}
            <div id="qr-scanner-region" ref={scannerRef} style={{ width: '100%' }}></div>
            {!scanning && !error && (
              <div className="py-4">
                <div className="spinner-border text-success"></div>
                <p className="text-muted mt-2">Starting camera...</p>
              </div>
            )}
            <p className="text-muted small mt-2">Point your camera at a resource QR code</p>
          </div>
        </div>
      </div>
    </div>
  );
}
