import { Container, getContainer } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

export class NexusBrainContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "30m";
  pingEndpoint = "api/health";

  envVars = {
    OPENAI_API_KEY: env.OPENAI_API_KEY,
    NEXUS_MODEL: env.NEXUS_MODEL,
    NEXUS_API_TOKEN: env.NEXUS_API_TOKEN,
    HOST: "0.0.0.0",
    PORT: "8080"
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health" || url.pathname === "/api/health" || url.pathname === "/api/chat") {
      return getContainer(env.NEXUS_BRAIN, "hilal").fetch(request);
    }

    return new Response("Nexus brain is online.", { status: 200 });
  }
};
