import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

// One player per comparison list; never synthesize speech or autoplay a sample.
export default function VoicePreview({ voices = [], selected, onSelect, disabled = false, compact = false }) {
  const player = useRef(null);
  const generation = useRef(0);
  const [playing, setPlaying] = useState(null);
  const [error, setError] = useState("");
  const stop = () => {
    generation.current += 1;
    if (player.current) {
      player.current.onended = null;
      player.current.onerror = null;
      player.current.pause();
      player.current.removeAttribute("src");
      player.current.load();
      player.current = null;
    }
  };
  useEffect(() => () => { stop(); }, []);
  const preview = async (voice) => {
    stop(); setPlaying(null); setError("");
    if (playing === voice.key) return;
    const current = generation.current;
    try {
      if (!/^[a-z]+$/.test(voice.key) || voice.preview_path !== `/assistant-voice-samples/${voice.key}.wav`) throw new Error("Invalid preview");
      const audio = new Audio(`${process.env.PUBLIC_URL || ""}${voice.preview_path}`);
      player.current = audio;
      audio.preload = "none";
      audio.onerror = () => {
        if (current !== generation.current) return;
        stop(); setPlaying(null); setError("This sample could not play. Check your speaker or try again. No AI request was made.");
      };
      audio.onended = () => { if (current === generation.current) { stop(); setPlaying(null); } };
      setPlaying(voice.key);
      await audio.play();
    } catch {
      if (current === generation.current) {
        stop(); setPlaying(null); setError("This sample could not play. Check your speaker or try again. No AI request was made.");
      }
    }
  };
  const items = compact ? voices.filter((voice) => voice.key === selected) : voices;
  return <div className="space-y-2" data-testid="assistant-voice-choices">
    <p className="text-sm">Prerecorded AI voice samples. Previewing does not select a voice or use AI credits. Personality does not change these recordings.</p>
    {error && <p role="alert">{error}</p>}
    <div className={compact ? "space-y-2" : "grid gap-2 sm:grid-cols-2"}>
      {items.map((voice) => <div key={voice.key} className="flex items-center justify-between gap-2 rounded border p-2">
        {onSelect ? <label className="flex items-center gap-2"><input type="radio" name="assistant-voice" value={voice.key} checked={selected === voice.key} disabled={disabled} onChange={() => onSelect(voice.key)} />{voice.name}</label> : <span>{voice.name}</span>}
        <Button variant="outline" size="sm" aria-label={`${playing === voice.key ? "Stop" : "Preview"} ${voice.name}`} onClick={() => preview(voice)}>{playing === voice.key ? "Stop sample" : "Preview"}</Button>
      </div>)}
    </div>
    <span role="status" className="text-sm">{playing ? `Playing ${voices.find((v) => v.key === playing)?.name || playing}` : "Preview stopped"}</span>
  </div>;
}
