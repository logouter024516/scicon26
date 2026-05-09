import { useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';

export function PhoneSenderPage() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const initialSessionId = params.get('session')?.trim() ?? '';
  const [sessionId, setSessionId] = useState(initialSessionId);
  const [sessionOk, setSessionOk] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentCount, setSentCount] = useState(0);
  const [cameraReady, setCameraReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    async function check() {
      if (!sessionId.trim()) {
        setSessionOk(false);
        return;
      }
      try {
        const r = await apiClient.phoneSessionExists(sessionId.trim());
        setSessionOk(Boolean(r.ok));
      } catch {
        setSessionOk(false);
      }
    }
    void check();
  }, [sessionId]);

  async function startCamera() {
    if (!sessionId.trim()) {
      setError('세션 ID가 없습니다. PC에서 연결 링크를 다시 열어 주세요.');
      return;
    }
    setError(null);
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    });
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
    }
    setCameraReady(true);
  }

  function stopCamera() {
    if (videoRef.current) videoRef.current.srcObject = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setCameraReady(false);
  }

  async function captureBlob(): Promise<Blob | null> {
    const video = videoRef.current;
    if (!video || video.videoWidth <= 0 || video.videoHeight <= 0) return null;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise<Blob | null>((resolve) => canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.82));
  }

  async function startSending() {
    if (running) return;
    try {
      if (!cameraReady) {
        await startCamera();
      }
      setRunning(true);
      timerRef.current = window.setInterval(async () => {
        try {
          const blob = await captureBlob();
          if (!blob) return;
          await apiClient.uploadPhoneFrame(sessionId.trim(), blob);
          setSentCount((v) => v + 1);
        } catch {
          // keep trying
        }
      }, 240);
    } catch (e) {
      setError(e instanceof Error ? e.message : '카메라 시작 실패');
    }
  }

  function stopSending() {
    setRunning(false);
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  useEffect(() => {
    return () => {
      stopSending();
      stopCamera();
    };
  }, []);

  return (
    <section className="page-shell" style={{ maxWidth: 860, margin: '0 auto' }}>
      <h2 className="section-title">Phone Camera Bridge</h2>
      <p className="panel-subtitle">Android / iPhone 공통 연결 페이지</p>

      <div className="feature-card panel">
        <div className="field-row">
          <p><strong>Session</strong>: {sessionId || '-'}</p>
          <input
            className="ui-input"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="PC 화면의 Session ID 입력"
          />
          <p className="muted">상태: {sessionOk ? '유효한 세션' : '세션 확인 필요'}</p>
        </div>
        <p><strong>Status</strong>: {running ? 'Streaming' : 'Idle'}</p>
        <p><strong>Frames sent</strong>: {sentCount}</p>

        <div className="preview-shell live-preview-shell" style={{ marginTop: 10 }}>
          <video ref={videoRef} className="preview-image" playsInline muted autoPlay />
        </div>

        <div className="btn-row" style={{ marginTop: 12 }}>
          <Button className="w-full btn-intent-start" onClick={() => void startSending()} disabled={running || !sessionId.trim() || !sessionOk}>
            Start Phone Stream
          </Button>
          <Button className="w-full btn-intent-stop" variant="outline" onClick={stopSending} disabled={!running}>
            Stop Phone Stream
          </Button>
        </div>

        {error && <p className="error" style={{ marginTop: 10 }}>{error}</p>}
      </div>
    </section>
  );
}
