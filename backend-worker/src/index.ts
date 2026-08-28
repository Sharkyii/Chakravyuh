import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  FASTAPI_CONTAINER: DurableObjectNamespace<FastApiContainer>;
  GOOGLE_GEMINI_API_KEY?: string;
}

export class FastApiContainer extends Container<Env> {
  defaultPort = 8000;
  sleepAfter = "10m";

  constructor(ctx: DurableObject["ctx"], env: Env) {
    super(ctx, env);
    if (env.GOOGLE_GEMINI_API_KEY) {
      this.envVars = { GOOGLE_GEMINI_API_KEY: env.GOOGLE_GEMINI_API_KEY };
    }
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = getContainer(env.FASTAPI_CONTAINER);
    return container.fetch(request);
  },
};
