import "@testing-library/jest-dom";
import { TextEncoder, TextDecoder } from "util";

// Provide a stable REACT_APP_BACKEND_URL for tests (lib/api reads this at import).
process.env.REACT_APP_BACKEND_URL = "http://localhost";

// jsdom 16 (bundled with react-scripts 5) does not expose TextEncoder/Decoder
// on `globalThis`, which react-router 7 requires at module-load time.
if (typeof globalThis.TextEncoder === "undefined") globalThis.TextEncoder = TextEncoder;
if (typeof globalThis.TextDecoder === "undefined") globalThis.TextDecoder = TextDecoder;

// jsdom lacks crypto.randomUUID — polyfill for components that use it for
// Idempotency-Keys (POs, receiving, physical count, transfer).
if (!global.crypto) global.crypto = {};
if (!global.crypto.randomUUID) {
  global.crypto.randomUUID = () => "test-uuid-" + Math.random().toString(36).slice(2, 10);
}
