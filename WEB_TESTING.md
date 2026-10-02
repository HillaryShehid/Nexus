# Cloudflare test site for personal Nexus

This is the personal-only Nexus browser interface. It is designed for Cloudflare Pages while the Python Nexus brain remains behind a private API.

## Architecture

Browser -> Cloudflare Pages -> Pages Functions /api/* -> Cloudflare Worker -> NexusBrainContainer -> NexusCore / NexusBrain

Cloudflare Pages supports static HTML and Pages Functions. The Functions in this project proxy /api/chat and /api/health to the protected Python API.

## Cloudflare setup

Use these Pages settings:
- Production branch: main
- Build command: exit 0
- Build output directory: web

Pages Functions live in the root functions/ directory.

Add these in Workers & Pages -> your project -> Settings -> Variables and Secrets:
- NEXUS_API_URL: HTTPS base URL of the server running the Nexus Python API.
- NEXUS_API_TOKEN: a long random secret shared only between Cloudflare Pages Functions and the Nexus API.

Store NEXUS_API_TOKEN as an encrypted Secret. Do not put it in web/app.js or another browser-visible file.

## Protect the site

Because this is your personal Nexus, protect the Pages site with Cloudflare Access. That keeps random visitors from using the personal AI endpoint.

## Nexus API server

The Python API is packaged into the Cloudflare Container under brain/. The container listens on 0.0.0.0:8080 and requires the same NEXUS_API_TOKEN sent by the Pages Function.

Cloudflare Containers are a Workers Paid feature. Configure the brain Worker from the brain/ directory using Workers Builds, then set its OPENAI_API_KEY, NEXUS_MODEL, and NEXUS_API_TOKEN secrets.

Set the Pages project's NEXUS_API_URL to the deployed brain Worker's workers.dev URL. Do not expose the Python API as a separate public server.

## Voice

The website includes:
- microphone voice input
- spoken Nexus responses
- optional read-aloud mode
- responsive mobile UI

This is the first testable browser voice bridge, not yet the full always-ready Nexus voice system. Wake-word detection, continuous listening, interruption handling, real AirPods routing, and dedicated local speech hardware remain future voice work.

## Deployment note

Cloudflare Pages hosts the browser UI and Pages Functions. The personal Python brain is deployed separately as a Cloudflare Container Worker because the existing brain uses a full Python/Linux runtime.

## Current scope

Included: personal Nexus chat, browser voice, protected API proxy, real Nexus Python brain connection.

Not included: business/CRM features, sales/calling systems, business website builder, payments, or business automation.