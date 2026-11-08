// This fixture is a complete, read-only source snapshot. File boundaries are comments.

// file: upload-port.ts
export type Ticket = string & { readonly ticket: unique symbol };
export type Receipt = Readonly<{ objectKey: string; length: number }>;
export class TemporaryUploadFailure extends Error {}
export interface UploadPort {
  // prepare is idempotent for an objectKey and payload.
  prepare(objectKey: string, payload: Uint8Array): Promise<Ticket>;
  // push may fail transiently; retrying the SAME ticket is safe.
  push(ticket: Ticket): Promise<void>;
  // finish is legal only after push has succeeded.
  finish(ticket: Ticket): Promise<Receipt>;
}

// file: upload-relay.ts
export class UploadRelay implements UploadPort {
  constructor(private readonly port: UploadPort) {}
  prepare(key: string, bytes: Uint8Array) { return this.port.prepare(key, bytes); }
  push(ticket: Ticket) { return this.port.push(ticket); }
  finish(ticket: Ticket) { return this.port.finish(ticket); }
}

// file: callers-before.ts
export async function publishInvoice(port: UploadPort, id: string, pdf: Uint8Array) {
  const ticket = await port.prepare("invoice/" + id, pdf);
  for (let attempt = 1; ; attempt++) {
    try { await port.push(ticket); break; }
    catch (e) { if (!(e instanceof TemporaryUploadFailure) || attempt === 3) throw e; }
  }
  return port.finish(ticket);
}
export async function publishPreview(port: UploadPort, id: string, png: Uint8Array) {
  const ticket = await port.prepare("preview/" + id, png);
  for (let attempt = 1; ; attempt++) {
    try { await port.push(ticket); break; }
    catch (e) { if (!(e instanceof TemporaryUploadFailure) || attempt === 3) throw e; }
  }
  return port.finish(ticket);
}

// file: one-method-proposal.ts
type Inputs = { prepare: [string, Uint8Array]; push: [Ticket]; finish: [Ticket] };
type Outputs = { prepare: Ticket; push: void; finish: Receipt };
export class UploadChannel {
  constructor(private readonly port: UploadPort) {}
  // This method is the proposal's entire public API.
  exchange<K extends keyof Inputs>(operation: K, ...args: Inputs[K]): Promise<Outputs[K]> {
    const action = this.port[operation].bind(this.port);
    return (action as (...values: Inputs[K]) => Promise<Outputs[K]>)(...args);
  }
}
export async function invoiceViaChannel(channel: UploadChannel, id: string, pdf: Uint8Array) {
  const ticket = await channel.exchange("prepare", "invoice/" + id, pdf);
  for (let attempt = 1; ; attempt++) {
    try { await channel.exchange("push", ticket); break; }
    catch (e) { if (!(e instanceof TemporaryUploadFailure) || attempt === 3) throw e; }
  }
  return channel.exchange("finish", ticket);
}
// previewViaChannel is mechanically identical, with the preview key and PNG payload.

// file: publisher-proposal.ts
export class Publisher {
  constructor(private readonly port: UploadPort) {}
  async publish(key: string, bytes: Uint8Array): Promise<Receipt> {
    const ticket = await this.port.prepare(key, bytes);
    for (let attempt = 1; ; attempt++) {
      try { await this.port.push(ticket); break; }
      catch (e) { if (!(e instanceof TemporaryUploadFailure) || attempt === 3) throw e; }
    }
    return this.port.finish(ticket);
  }
}
export function invoiceViaPublisher(publisher: Publisher, id: string, pdf: Uint8Array) {
  return publisher.publish("invoice/" + id, pdf);
}
export function previewViaPublisher(publisher: Publisher, id: string, png: Uint8Array) {
  return publisher.publish("preview/" + id, png);
}

// file: composition.ts
export function currentWiring(vendor: UploadPort): UploadPort { return new UploadRelay(vendor); }
// UploadRelay has no other instances, decorators, policies, tests, or consumers.

// file: upload.test.ts (recorded assertions; test harness omitted)
export const existingChecks = [
  "invoice success prepares then pushes then finishes",
  "preview success prepares then pushes then finishes",
  "two TemporaryUploadFailure errors then success cause three pushes of the SAME ticket",
  "a third temporary failure propagates and finish is not called",
  "a permanent error propagates immediately and finish is not called"
];
