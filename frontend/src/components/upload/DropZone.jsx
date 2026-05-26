/*
 * components/upload/DropZone.jsx — drag-and-drop file upload area.
 *
 * Key concepts:
 *   onDragOver: fires repeatedly while dragging over an element. We call
 *     e.preventDefault() to tell the browser "I will handle the drop"
 *     (without this, the browser would navigate to the dropped file).
 *
 *   onDrop: fires when the user releases the file.
 *     e.dataTransfer.files[0] gives us the File object.
 *
 *   <input type="file" hidden>: a hidden file input that the user can
 *     trigger by clicking anywhere on the dropzone.
 *
 *   useRef: a React ref gives us a reference to the DOM element so we
 *     can programmatically call inputRef.current.click().
 */
import { useRef, useState } from "react";
import { Upload, FileText, X, Lock } from "lucide-react";
import { formatFileSize, fileTypeInfo } from "../../utils/formatters.js";

const ACCEPTED = ".pdf,.jpg,.jpeg,.png,.tiff,.webp,.docx";

export default function DropZone({ onFileSelect, selectedFile, maxSizeMB = 10 }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [password, setPassword] = useState("");

  // ── Drag event handlers ────────────────────────────────────────────────────
  const handleDragOver = (e) => {
    e.preventDefault();       // required to allow drop
    setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    // Only trigger if leaving the dropzone itself (not a child element)
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragging(false);
    }
  };
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFileSelect(file, password);
  };

  // ── Click handler: open native file picker ─────────────────────────────────
  const handleClick = () => inputRef.current?.click();

  // ── File input change handler ─────────────────────────────────────────────
  const handleInputChange = (e) => {
    const file = e.target.files[0];
    if (file) onFileSelect(file, password);
    // Reset input so the same file can be re-selected
    e.target.value = "";
  };

  const typeInfo = selectedFile ? fileTypeInfo(selectedFile.type) : null;

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        className={`
          relative flex flex-col items-center justify-center
          min-h-56 rounded-2xl border-2 border-dashed cursor-pointer
          transition-all duration-200 select-none
          ${isDragging
            ? "border-indigo-500 bg-indigo-50 scale-[1.01]"
            : selectedFile
              ? "border-indigo-300 bg-indigo-50/50"
              : "border-gray-300 bg-white hover:border-indigo-400 hover:bg-gray-50"
          }
        `}
      >
        {/* Hidden file input */}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="hidden"
          onChange={handleInputChange}
        />

        {selectedFile ? (
          /* ── File selected state ── */
          <div className="flex flex-col items-center gap-3 px-6 py-8 text-center">
            <div className="w-14 h-14 bg-indigo-100 rounded-2xl flex items-center justify-center">
              <FileText className={`w-7 h-7 ${typeInfo?.color || "text-indigo-600"}`} />
            </div>
            <div>
              <p className="font-semibold text-gray-900 text-sm truncate max-w-xs">{selectedFile.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {typeInfo?.label} &bull; {formatFileSize(selectedFile.size)}
              </p>
            </div>
            <p className="text-xs text-indigo-600 font-medium">
              Click or drop a different file to replace
            </p>
          </div>
        ) : (
          /* ── Empty state ── */
          <div className="flex flex-col items-center gap-4 px-6 py-10 text-center pointer-events-none">
            <div className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-colors ${
              isDragging ? "bg-indigo-200" : "bg-gray-100"
            }`}>
              <Upload className={`w-8 h-8 transition-colors ${
                isDragging ? "text-indigo-600" : "text-gray-400"
              }`} />
            </div>
            <div>
              <p className="font-semibold text-gray-700 text-base">
                {isDragging ? "Release to upload" : "Drop your document here"}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                or <span className="text-indigo-600 font-medium">click to browse</span>
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-1.5">
              {["PDF", "JPEG", "PNG", "TIFF", "WebP", "DOCX"].map((t) => (
                <span key={t} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded font-medium">
                  {t}
                </span>
              ))}
            </div>
            <p className="text-xs text-gray-400">Maximum file size: {maxSizeMB} MB</p>
          </div>
        )}
      </div>

      {/* Password field for encrypted PDFs */}
      <div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setShowPassword((v) => !v); }}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
        >
          <Lock className="w-3.5 h-3.5" />
          {showPassword ? "Hide password field" : "Add PDF password (optional)"}
        </button>
        {showPassword && (
          <div className="mt-2">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter PDF password"
              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2
                         focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                         placeholder:text-gray-400"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}
      </div>
    </div>
  );
}
