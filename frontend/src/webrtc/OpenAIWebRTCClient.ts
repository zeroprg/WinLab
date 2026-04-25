export type RealtimeEventHandler = (event: Record<string, unknown>) => void;

interface SessionResponse {
  sdp: string;
  context: Array<{ role: "user" | "assistant"; text: string }>;
  /** Backend interview_sessions.id — pass to POST /api/message so transcripts attach to this session. */
  session_id?: string;
}

export class OpenAIWebRTCClient {
  private pc: RTCPeerConnection | null = null;
  private dc: RTCDataChannel | null = null;
  private stream: MediaStream | null = null;
  private audioEl: HTMLAudioElement | null = null;
  private eventHandler: RealtimeEventHandler | null = null;
  private sessionEndpoint = "/api/realtime/session";

  setEventHandler(handler: RealtimeEventHandler): void {
    this.eventHandler = handler;
  }

  async connect(endpoint?: string, userId = "guest", locale = ""): Promise<{ session_id?: string }> {
    if (endpoint) this.sessionEndpoint = endpoint;

    this.pc = new RTCPeerConnection();

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.stream = stream;
    stream.getTracks().forEach((track) => this.pc!.addTrack(track, stream));

    this.audioEl = document.createElement("audio");
    this.audioEl.autoplay = true;
    this.pc.ontrack = (ev) => {
      this.audioEl!.srcObject = ev.streams[0] ?? new MediaStream([ev.track]);
    };

    this.dc = this.pc.createDataChannel("oai-events");
    this.dc.addEventListener("message", (ev) => {
      try {
        const parsed = JSON.parse(ev.data as string);
        this.eventHandler?.(parsed);
      } catch {
        // ignore non-JSON messages
      }
    });

    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);

    const sdp = this.pc.localDescription?.sdp;
    if (!sdp) throw new Error("Failed to create local SDP");

    const params = new URLSearchParams({ user_id: userId });
    if (locale) params.set("locale", locale);
    const url = `${this.sessionEndpoint}?${params.toString()}`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: sdp,
    });

    if (!res.ok) {
      throw new Error(`Session failed: ${res.status}`);
    }

    const data = (await res.json()) as SessionResponse;
    await this.pc.setRemoteDescription({ type: "answer", sdp: data.sdp });

    await this.waitForDataChannel();

    if (data.context?.length) {
      this.injectHistory(data.context);
    }

    const session_id =
      typeof data.session_id === "string" && data.session_id.length > 0
        ? data.session_id
        : undefined;
    return { session_id };
  }

  private waitForDataChannel(timeoutMs = 5000): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.dc) return reject(new Error("No data channel"));
      if (this.dc.readyState === "open") return resolve();

      const timer = setTimeout(() => {
        reject(new Error("Data channel open timeout"));
      }, timeoutMs);

      this.dc.addEventListener(
        "open",
        () => {
          clearTimeout(timer);
          resolve();
        },
        { once: true },
      );
    });
  }

  private injectHistory(history: SessionResponse["context"]): void {
    for (const msg of history) {
      this.sendEvent({
        type: "conversation.item.create",
        item: {
          type: "message",
          role: msg.role,
          content: [{ type: "input_text", text: msg.text }],
        },
      });
    }
  }

  sendEvent(event: object): void {
    const payload = JSON.stringify(event);
    if (!this.dc || this.dc.readyState !== "open") {
      console.warn("DataChannel not open, dropping event:", event);
      return;
    }
    this.dc.send(payload);
  }

  getConnectionState(): string {
    return this.pc?.connectionState ?? "closed";
  }

  disconnect(): void {
    if (this.audioEl) {
      this.audioEl.pause();
      this.audioEl.srcObject = null;
      this.audioEl = null;
    }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.dc?.close();
    this.dc = null;
    this.pc?.close();
    this.pc = null;
  }
}

export default OpenAIWebRTCClient;
