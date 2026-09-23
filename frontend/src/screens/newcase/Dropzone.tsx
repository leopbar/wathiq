import { useRef, useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";
import { FileText, Image as ImageIcon, Paperclip, UploadCloud, X } from "lucide-react";
import { ACCEPTED_EXTENSIONS, ACCEPTED_MIME, MAX_FILES, MAX_FILE_BYTES } from "@/lib/constants";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";

export interface PickedFile {
  id: string;
  file: File;
}

/**
 * A list key only needs to be unique within this list.
 * `crypto.randomUUID()` exists only in a secure context, so it is missing when the app is served
 * over plain HTTP from anything other than localhost — reaching for it directly threw there and
 * silently dropped the file.
 */
function uniqueSuffix(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function Dropzone({
  files,
  onChange,
  disabled,
}: {
  files: PickedFile[];
  onChange: (files: PickedFile[]) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const add = (incoming: FileList | null) => {
    if (!incoming) return;
    const accepted: PickedFile[] = [...files];
    const problems: string[] = [];

    for (const file of Array.from(incoming)) {
      if (accepted.length >= MAX_FILES) {
        problems.push(t("dropzone.tooMany", { count: MAX_FILES }));
        break;
      }
      let problem: string | null = null;
      if (!ACCEPTED_MIME.includes(file.type as (typeof ACCEPTED_MIME)[number])) {
        problem = t("dropzone.invalidType", { name: file.name });
      } else if (file.size > MAX_FILE_BYTES) {
        problem = t("dropzone.tooLarge", {
          name: file.name,
          size: formatBytes(MAX_FILE_BYTES),
        });
      } else if (accepted.some((f) => f.file.name === file.name && f.file.size === file.size)) {
        problem = t("dropzone.duplicate", { name: file.name });
      }
      if (problem) {
        problems.push(problem);
        continue;
      }
      accepted.push({ id: `${file.name}-${file.size}-${uniqueSuffix()}`, file });
    }

    setErrors(problems);
    onChange(accepted);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    add(event.dataTransfer.files);
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "rounded-[var(--radius-lg)] border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragging ? "border-primary bg-primary-soft/50" : "border-border bg-surface-2/40",
          disabled && "opacity-60",
        )}
      >
        <span className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-surface text-primary shadow-card">
          <UploadCloud className="h-5 w-5" aria-hidden />
        </span>
        <p className="text-body font-medium text-ink">{t("dropzone.title")}</p>
        <p className="mx-auto mt-1 max-w-sm text-small text-ink-2">
          {t("dropzone.description", { size: formatBytes(MAX_FILE_BYTES) })}
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="mt-4"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          <Paperclip className="h-3.5 w-3.5" aria-hidden />
          {t("dropzone.choose")}
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS}
          className="sr-only"
          aria-label={t("dropzone.chooseLabel")}
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {errors.length > 0 ? (
        <ul role="alert" className="space-y-1">
          {errors.map((error) => (
            <li key={error} className="text-caption text-danger">
              {error}
            </li>
          ))}
        </ul>
      ) : null}

      {files.length > 0 ? (
        <ul className="space-y-2">
          {files.map((picked) => {
            const Icon = picked.file.type.startsWith("image/") ? ImageIcon : FileText;
            return (
              <li
                key={picked.id}
                className="flex items-center gap-3 rounded-[var(--radius)] border border-border bg-surface px-3 py-2"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-surface-2 text-ink-2">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-small font-medium text-ink">{picked.file.name}</p>
                  <p className="text-caption text-ink-2 tabular">{formatBytes(picked.file.size)}</p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="iconSm"
                  disabled={disabled}
                  aria-label={t("dropzone.remove", { name: picked.file.name })}
                  onClick={() => onChange(files.filter((f) => f.id !== picked.id))}
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </Button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
