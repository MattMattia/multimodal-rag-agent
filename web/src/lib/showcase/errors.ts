/** Expected, user-facing failures of the showcase engine, mapped by the BFF to an HTTP status. */
export class ShowcaseError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ShowcaseError";
  }
}
