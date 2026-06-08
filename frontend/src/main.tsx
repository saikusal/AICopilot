import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Eraser,
  Mic,
  Pause,
  Play,
  RefreshCcw,
  Send,
  Scissors,
  Square
} from "lucide-react";
import { CopilotResponse, resetSession, sendAudioChunk, sendText } from "./api";
import "./styles.css";

type Status = "idle" | "listening" | "paused" | "processing" | "error";
type ListenMode = "auto" | "hold";

function getSessionId(): string {
  const existing = localStorage.getItem("interview-copilot-session");
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem("interview-copilot-session", created);
  return created;
}

function App() {
  const sessionId = useMemo(getSessionId, []);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const pauseTimerRef = useRef<number | null>(null);
  const chunkTimerRef = useRef<number | null>(null);
  const listeningRef = useRef(false);
  const chunksRef = useRef<Blob[]>([]);

  const [status, setStatus] = useState<Status>("idle");
  const [listenMode, setListenMode] = useState<ListenMode>("auto");
  const [transcript, setTranscript] = useState("");
  const [question, setQuestion] = useState("");
  const [questionType, setQuestionType] = useState("");
  const [answer, setAnswer] = useState("");
  const [message, setMessage] = useState("Tap Listen when the interviewer starts speaking.");
  const [error, setError] = useState("");
  const [manualText, setManualText] = useState("");

  useEffect(() => {
    return () => stopListening();
  }, []);

  function applyResponse(data: CopilotResponse) {
    setTranscript(data.transcript || "");
    if (data.question) setQuestion(data.question);
    if (data.question_type) setQuestionType(data.question_type.replace("_", " "));
    if (data.answer) setAnswer(data.answer);
    if (data.message) setMessage(data.message);
    if (data.should_pause) {
      setMessage("Answer ready. Mic paused so your response is ignored.");
      pauseAfterAnswer();
    }
  }

  async function startListening() {
    clearPauseTimer();
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      streamRef.current = stream;
      listeningRef.current = true;
      setStatus("listening");
      if (listenMode === "hold") {
        setMessage("Recording. Release Listen when the question is complete.");
        startRecordingChunk(stream, mimeType, true);
      } else {
        setMessage("Listening. It will send complete audio every 10 seconds.");
        startRecordingChunk(stream, mimeType, false);
      }
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Microphone permission failed");
    }
  }

  function startRecordingChunk(stream: MediaStream, mimeType: string, sendOnStop: boolean) {
    if (!listeningRef.current) return;
    chunksRef.current = [];
    const recorder = new MediaRecorder(stream, { mimeType });
    recorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data.size) chunksRef.current.push(event.data);
    };

    recorder.onstop = async () => {
      const chunks = chunksRef.current;
      chunksRef.current = [];

      if (chunkTimerRef.current) {
        window.clearTimeout(chunkTimerRef.current);
        chunkTimerRef.current = null;
      }

      if (!sendOnStop && !listeningRef.current) return;

      if (chunks.length === 0) {
        if (listenMode === "hold") {
          setStatus("idle");
          setMessage("No audio captured. Hold Listen while the question is being asked.");
        } else if (listeningRef.current) {
          startRecordingChunk(stream, mimeType, false);
        }
        return;
      }

      const audio = new Blob(chunks, { type: mimeType });
      setStatus("processing");
      setMessage("Processing audio...");
      try {
        const data = await sendAudioChunk(sessionId, audio, "normal", sendOnStop);
        applyResponse(data);
        if (sendOnStop) {
          stream.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
          listeningRef.current = false;
          setStatus(data.should_pause ? "paused" : "idle");
        } else if (!data.should_pause && listeningRef.current) {
          setStatus("listening");
          startRecordingChunk(stream, mimeType, false);
        }
      } catch (err) {
        if (!listeningRef.current) return;
        setStatus("error");
        setError(err instanceof Error ? err.message : "Audio upload failed");
      }
    };

    recorder.start();
    if (!sendOnStop) {
      chunkTimerRef.current = window.setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, 10000);
    }
  }

  function stopListening(nextStatus: Status = "paused") {
    clearPauseTimer();
    listeningRef.current = false;
    if (chunkTimerRef.current) {
      window.clearTimeout(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
    setStatus(nextStatus);
  }

  function pauseAfterAnswer() {
    stopListening("paused");
    pauseTimerRef.current = window.setTimeout(() => {
      setMessage("Ready for the next question. Tap Resume.");
    }, 15000);
  }

  function clearPauseTimer() {
    if (pauseTimerRef.current) {
      window.clearTimeout(pauseTimerRef.current);
      pauseTimerRef.current = null;
    }
  }

  async function submitManual(mode = "normal") {
    if (!manualText.trim() && mode !== "regenerate" && mode !== "short") return;
    setStatus("processing");
    setError("");
    try {
      const text = mode === "normal" ? manualText : question;
      const data = await sendText(sessionId, text, mode, true);
      applyResponse(data);
      setManualText("");
      setStatus("paused");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Answer generation failed");
    }
  }

  async function clearAll() {
    stopListening("idle");
    await resetSession(sessionId);
    setTranscript("");
    setQuestion("");
    setQuestionType("");
    setAnswer("");
    setManualText("");
    setMessage("Session cleared. Tap Listen for the next question.");
    setError("");
  }

  const statusLabel = status === "processing" ? "processing" : status;

  return (
    <main className="appShell">
      <header className="topBar">
        <div>
          <p className="eyebrow">AI Interview Copilot</p>
          <h1>Phone Assist</h1>
        </div>
        <div className={`statusPill ${status}`}>{statusLabel}</div>
      </header>

      <section className="controls">
        {listenMode === "hold" ? (
          <button
            className="primaryButton"
            disabled={status === "processing"}
            onPointerDown={startListening}
            onPointerUp={() => stopListening("processing")}
            onPointerCancel={() => stopListening("idle")}
            onPointerLeave={() => {
              if (status === "listening") stopListening("processing");
            }}
          >
            {status === "listening" ? <Pause size={18} /> : <Mic size={18} />}
            {status === "listening" ? "Release to Send" : "Hold to Listen"}
          </button>
        ) : status === "listening" || status === "processing" ? (
          <button className="primaryButton" onClick={() => stopListening("paused")}>
            <Pause size={18} /> Pause
          </button>
        ) : (
          <button className="primaryButton" onClick={startListening}>
            <Mic size={18} /> {status === "paused" ? "Resume" : "Listen"}
          </button>
        )}
        <button className="iconButton" title="Stop" onClick={() => stopListening("idle")}>
          <Square size={18} />
        </button>
        <button className="iconButton" title="Clear session" onClick={clearAll}>
          <Eraser size={18} />
        </button>
      </section>

      <section className="modeToggle" aria-label="Listening mode">
        <button
          className={listenMode === "auto" ? "active" : ""}
          disabled={status === "listening" || status === "processing"}
          onClick={() => setListenMode("auto")}
        >
          Auto 10s
        </button>
        <button
          className={listenMode === "hold" ? "active" : ""}
          disabled={status === "listening" || status === "processing"}
          onClick={() => setListenMode("hold")}
        >
          Hold
        </button>
      </section>

      <p className="helperText">{error || message}</p>

      <section className="panel">
        <div className="panelHeader">
          <h2>Question</h2>
          {questionType && <span>{questionType}</span>}
        </div>
        <p className={question ? "questionText" : "emptyText"}>
          {question || "No question detected yet."}
        </p>
      </section>

      <section className="panel answerPanel">
        <div className="panelHeader">
          <h2>Answer</h2>
          <div className="miniActions">
            <button title="Regenerate" disabled={!question} onClick={() => submitManual("regenerate")}>
              <RefreshCcw size={16} />
            </button>
            <button title="Shorten" disabled={!question} onClick={() => submitManual("short")}>
              <Scissors size={16} />
            </button>
          </div>
        </div>
        <pre className={answer ? "answerText" : "emptyText"}>
          {answer || "Answer will appear here after the question is detected."}
        </pre>
      </section>

      <section className="panel">
        <div className="panelHeader">
          <h2>Live Transcript</h2>
        </div>
        <p className={transcript ? "transcriptText" : "emptyText"}>
          {transcript || "Transcript will build while listening."}
        </p>
      </section>

      <section className="manualBox">
        <textarea
          value={manualText}
          onChange={(event) => setManualText(event.target.value)}
          placeholder="Paste or type a question for testing..."
          rows={3}
        />
        <button onClick={() => submitManual()}>
          <Send size={17} /> Ask
        </button>
      </section>

      <nav className="bottomNav">
        <button className="active"><Play size={16} /> Live</button>
        <button><Mic size={16} /> Coding</button>
        <button><RefreshCcw size={16} /> History</button>
      </nav>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
