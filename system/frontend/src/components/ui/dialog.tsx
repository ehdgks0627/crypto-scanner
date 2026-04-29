import { X } from "lucide-react";
import { type KeyboardEvent, type PropsWithChildren, useEffect, useId, useRef } from "react";

import { Button } from "./button";

type DialogProps = PropsWithChildren<{
  open: boolean;
  title: string;
  onClose: () => void;
  closeDisabled?: boolean;
  describedBy?: string;
}>;

const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

export function Dialog({ open, title, onClose, closeDisabled = false, describedBy, children }: DialogProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const firstFocusable = panelRef.current?.querySelector<HTMLElement>(focusableSelector);
    (firstFocusable ?? panelRef.current)?.focus();
    return () => previousFocusRef.current?.focus();
  }, [open]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && !closeDisabled) {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") {
      return;
    }
    const focusable = Array.from(panelRef.current?.querySelectorAll<HTMLElement>(focusableSelector) ?? []);
    if (focusable.length === 0) {
      event.preventDefault();
      panelRef.current?.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!focusable.includes(document.activeElement as HTMLElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  if (!open) {
    return null;
  }
  return (
    <div className="ui-dialog" onKeyDown={handleKeyDown}>
      <div className="ui-dialog__backdrop" onClick={closeDisabled ? undefined : onClose} />
      <div ref={panelRef} className="ui-dialog__panel" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={describedBy} tabIndex={-1}>
        <div className="ui-dialog__header">
          <h2 id={titleId}>{title}</h2>
          <Button type="button" size="icon" variant="ghost" disabled={closeDisabled} onClick={onClose} aria-label="닫기">
            <X size={16} />
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}
