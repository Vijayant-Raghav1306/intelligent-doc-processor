"""
NLP service — spaCy model loading and lifecycle management.

Design decisions
────────────────
  SINGLETON pattern:  the model is loaded ONCE at startup and reused for
  every request.  spaCy models are large (~12-580MB) and take 1-3 seconds
  to load.  Loading per-request would make the API unusably slow.

  OPTIONAL / DEGRADED MODE:  if spaCy or the model is not installed, the
  system logs a warning and continues with regex-only extraction.  Nothing
  in the extraction layer should hard-fail because spaCy is absent.

  THREAD-SAFETY:  spaCy Doc objects are NOT shared between requests — each
  call to nlp(text) creates a new Doc.  The Language object (the model
  itself) is read-only and safe to share across threads.

  MEMORY:
    en_core_web_sm  ≈  12 MB   (fast, recommended start)
    en_core_web_md  ≈  43 MB   (+ word vectors, better similarity)
    en_core_web_lg  ≈ 587 MB   (best vectors, slow to load)
    en_core_web_trf ≈ 440 MB   (transformer, best NER accuracy)

  PIPELINE COMPONENTS loaded:
    tok2vec, tagger, parser, senter, ner, attribute_ruler, lemmatizer
  We disable 'parser' and 'senter' at inference time (not needed for NER)
  to save ~30% CPU per document.

Usage
─────
  from app.extraction.nlp_service import load_nlp, get_nlp

  # At startup (call once):
  load_nlp()

  # In extractors (call per request):
  nlp = get_nlp()          # returns Language | None
  if nlp:
      doc = nlp(text)      # spaCy inference
"""
import time
from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Module-level singleton — None until load_nlp() is called
_nlp = None   # type: ignore[assignment]


def load_nlp() -> bool:
    """
    Load the spaCy language model into the module-level singleton.

    Called once at FastAPI startup (app/main.py lifespan).

    Returns:
        True  — model loaded successfully, NLP extraction is available.
        False — model unavailable; system runs in regex-only mode.

    Side effects:
        Sets the module-level _nlp variable.
        Logs timing and model metadata.
    """
    global _nlp

    model_name = settings.spacy_model

    # Empty model name → operator explicitly opted out of NLP
    if not model_name:
        logger.info("NLP disabled by config (spacy_model is empty)")
        return False

    try:
        import spacy  # local import keeps spaCy optional at import time

        t0 = time.perf_counter()

        # Disable pipeline components we don't use for NER.
        # 'parser' builds the dependency tree — expensive, not needed here.
        # 'senter' does sentence segmentation — also not needed.
        # Keeping 'tagger' and 'ner' (both needed for NER accuracy).
        _nlp = spacy.load(model_name, exclude=["parser", "senter"])

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

        logger.info(
            "spaCy model loaded",
            extra={
                "model": model_name,
                "pipeline": str(_nlp.pipe_names),
                "load_ms": elapsed_ms,
            },
        )
        return True

    except OSError:
        # Model name not found — user forgot to run `python -m spacy download ...`
        logger.warning(
            "spaCy model not found — running in regex-only mode. "
            f"Fix: python -m spacy download {model_name}",
            extra={"model": model_name},
        )
        return False

    except ImportError:
        logger.warning(
            "spaCy not installed — running in regex-only mode. "
            "Fix: pip install spacy",
        )
        return False

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Unexpected error loading spaCy model",
            extra={"model": model_name, "error": repr(exc)},
        )
        return False


def get_nlp():
    """
    Return the loaded spaCy Language object, or None if unavailable.

    Use at the start of every extraction call:
        nlp = get_nlp()
        doc = nlp(text) if nlp else None

    Never cache the return value — always call get_nlp() so that
    a future reload (e.g. model hot-swap) propagates automatically.
    """
    return _nlp


def is_nlp_available() -> bool:
    """Return True if the NLP model is loaded and ready."""
    return _nlp is not None
