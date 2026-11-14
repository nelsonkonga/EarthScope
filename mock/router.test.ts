import { describe, expect, it } from "vitest";
import handler from "../api/index";
import { dispatch } from "./router";

function invoke(method: string, url: string, body?: unknown) {
  return new Promise<{ status: number; json: { zones?: { name: string }[]; message?: { text: string } } }>((resolve) => {
    const res = {
      statusCode: 0,
      setHeader() {},
      end(payload: string) {
        resolve({ status: this.statusCode, json: JSON.parse(payload) as { zones?: { name: string }[]; message?: { text: string } } });
      },
    };
    void handler({ method, url, headers: { host: "localhost" }, body }, res);
  });
}

describe("fixture api", () => {
  it("lists the prototype cities", async () => {
    const result = await dispatch("GET", new URL("http://localhost/api/v1/zones"), undefined);
    expect(result.status).toBe(200);
    const names = (result.body as { zones: { name: string }[] }).zones.map((zone) => zone.name);
    expect(names).toContain("Yaoundé");
    expect(names).toContain("Accra");
  });

  it("keeps a portable assistant session usable without the instance that created it", async () => {
    const id = "es1-11111111-1111-4111-8111-111111111111";
    const session = await dispatch("GET", new URL(`http://localhost/api/v1/assistant/sessions/${id}`), undefined);
    expect(session.status).toBe(200);
    const message = await dispatch("POST", new URL(`http://localhost/api/v1/assistant/sessions/${id}/messages`), {
      text: "Quelles villes se réchauffent le plus rapidement ?",
      clientContext: {},
    });
    expect(message.status).toBe(200);
    expect((message.body as { message: { text: string } }).message.text.length).toBeGreaterThan(0);
  });

  it("serves the fixture through the Vercel function entry", async () => {
    const zones = await invoke("GET", "/api/v1/zones?q=lagos");
    expect(zones.status).toBe(200);
    expect(zones.json.zones?.map((zone) => zone.name)).toEqual(["Lagos"]);
    const message = await invoke("POST", "/api/v1/assistant/sessions/es1-22222222-2222-4222-8222-222222222222/messages", {
      text: "Paris",
      clientContext: {},
    });
    expect(message.status).toBe(200);
    expect(message.json.message?.text.length).toBeGreaterThan(0);
  });

  it("rejects an unknown session", async () => {
    const result = await dispatch("GET", new URL("http://localhost/api/v1/assistant/sessions/not-a-session"), undefined);
    expect(result.status).toBe(404);
  });
});
