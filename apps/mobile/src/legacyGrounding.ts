type ProviderMetadataRecord = { message: { metadata: Record<string, unknown> } };

export function hasEarlierUnverifiedGroqMessages(
  records: readonly ProviderMetadataRecord[],
): boolean {
  return records.some(({ message }) =>
    message.metadata.provider_version === "v1"
    && (message.metadata.provider === "groq-live-debate"
      || message.metadata.provider === "groq-live-judge"),
  );
}
