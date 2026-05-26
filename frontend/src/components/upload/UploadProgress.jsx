/*
 * components/upload/UploadProgress.jsx — shows upload + processing status.
 *
 * Shown when state is "uploading" or "processing".
 * Two distinct phases:
 *   uploading  → shows a real progress bar (% of bytes transferred)
 *   processing → shows an indeterminate spinner (server is crunching)
 */
import Spinner from "../ui/Spinner.jsx";
import ProgressBar from "../ui/ProgressBar.jsx";
import { Cpu } from "lucide-react";

const PROCESSING_STEPS = [
  "Running OCR on document...",
  "Extracting text content...",
  "Identifying invoice fields...",
  "Running NLP analysis...",
  "Computing confidence scores...",
];

export default function UploadProgress({ state, uploadProgress }) {
  return (
    <div className="card flex flex-col items-center gap-6 py-12">
      {state === "uploading" ? (
        <>
          <div className="w-14 h-14 bg-indigo-100 rounded-2xl flex items-center justify-center">
            <Spinner size="md" />
          </div>
          <div className="w-full max-w-sm">
            <ProgressBar value={uploadProgress} label="Uploading file..." />
          </div>
          <p className="text-sm text-gray-500">Sending document to server</p>
        </>
      ) : (
        <>
          {/* Processing state: indeterminate — server running OCR + NLP */}
          <div className="relative">
            <div className="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center">
              <Cpu className="w-8 h-8 text-indigo-600" />
            </div>
            <div className="absolute -top-1 -right-1">
              <Spinner size="sm" />
            </div>
          </div>

          <div className="text-center">
            <p className="font-semibold text-gray-900 text-base">Processing document</p>
            <p className="text-sm text-gray-500 mt-1">
              OCR + NLP extraction running. This can take 10-30 seconds.
            </p>
          </div>

          {/* Animated processing steps */}
          <div className="w-full max-w-sm space-y-2">
            {PROCESSING_STEPS.map((step, i) => (
              <div key={step} className="flex items-center gap-2.5">
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  i === 0 ? "bg-indigo-600 animate-pulse" : "bg-gray-300"
                }`} />
                <span className={`text-xs ${i === 0 ? "text-gray-700 font-medium" : "text-gray-400"}`}>
                  {step}
                </span>
              </div>
            ))}
          </div>

          {/* Indeterminate progress bar */}
          <div className="w-full max-w-sm h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-indigo-600 rounded-full animate-[shimmer_1.5s_ease-in-out_infinite]
                           w-1/3 translate-x-[-100%] animate-[progress-slide_1.5s_ease-in-out_infinite]"
                 style={{
                   animation: "progressSlide 1.5s ease-in-out infinite",
                 }}
            />
          </div>

          <style>{`
            @keyframes progressSlide {
              0%   { transform: translateX(-100%); width: 40%; }
              50%  { width: 60%; }
              100% { transform: translateX(350%); width: 40%; }
            }
          `}</style>
        </>
      )}
    </div>
  );
}
