export function JsonPreview({ value }: { value: unknown }) {
  return (
    <div className="json-preview">
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}
