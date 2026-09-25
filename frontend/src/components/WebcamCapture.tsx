import { useEffect, useRef, useState } from "react";

interface Props {
  onFrames?: (frames: string[]) => void;
  autoCapture?: number; // if set, capture this many frames automatically over a couple seconds
  onSingleCapture?: (frame: string) => void;
}

export default function WebcamCapture({ onFrames, autoCapture, onSingleCapture }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [captured, setCaptured] = useState<string[]>([]);
  const [capturing, setCapturing] = useState(false);

  useEffect(() => {
    let stream: MediaStream;
    navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 } })
      .then((s) => {
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
        setReady(true);
      })
      .catch(() => setError("Could not access webcam. Check browser permissions."));
    return () => { stream?.getTracks().forEach((t) => t.stop()); };
  }, []);

  const captureFrame = (): string => {
    const video = videoRef.current!;
    const canvas = canvasRef.current!;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(video, 0, 0);
    return canvas.toDataURL("image/jpeg", 0.85);
  };

  const captureOne = () => {
    const frame = captureFrame();
    if (onSingleCapture) onSingleCapture(frame);
  };

  const captureMulti = async () => {
    if (!autoCapture) return;
    setCapturing(true);
    const frames: string[] = [];
    for (let i = 0; i < autoCapture; i++) {
      await new Promise((r) => setTimeout(r, 400));
      frames.push(captureFrame());
    }
    setCaptured(frames);
    setCapturing(false);
    if (onFrames) onFrames(frames);
  };

  return (
    <div>
      {error && <p className="text-sm mb-2" style={{ color: "var(--color-danger)" }}>{error}</p>}
      <video ref={videoRef} autoPlay playsInline muted className="rounded border w-full max-w-sm mx-auto"
        style={{ borderColor: "var(--color-line)", transform: "scaleX(-1)" }} />
      <canvas ref={canvasRef} className="hidden" />
      <div className="flex justify-center gap-2 mt-3">
        {autoCapture ? (
          <button type="button" className="btn-primary" disabled={!ready || capturing} onClick={captureMulti}>
            {capturing ? "Capturing…" : `Capture ${autoCapture} frames`}
          </button>
        ) : (
          <button type="button" className="btn-primary" disabled={!ready} onClick={captureOne}>
            Capture & Verify
          </button>
        )}
      </div>
      {captured.length > 0 && (
        <p className="text-xs text-gray-400 text-center mt-2">{captured.length} frames captured.</p>
      )}
    </div>
  );
}
