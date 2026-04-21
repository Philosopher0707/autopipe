import { useMemo, useState } from 'react'
import { ImageOff } from 'lucide-react'
import { PanelWrapper } from '../PanelWrapper'
import type { PanelLayout } from '../WorkspaceContext'

interface MediaViewerProps {
  panel: PanelLayout
}

export function MediaViewer({ panel }: MediaViewerProps) {
  const { images: imageUrls } = useMemo(() => ({
    images: panel.config.images as string[] | undefined,
  }), [panel.config])

  const [selectedIdx, setSelectedIdx] = useState(0)

  const images = imageUrls ?? []

  return (
    <PanelWrapper panel={panel}>
      {images.length > 0 ? (
        <div className="flex flex-col h-full gap-2">
          <div className="flex-1 flex items-center justify-center bg-muted/30 rounded-lg overflow-hidden">
            <img
              src={images[selectedIdx]}
              alt={`Run media ${selectedIdx + 1}`}
              className="max-w-full max-h-full object-contain rounded"
              loading="lazy"
            />
          </div>

          {/* Thumbnails */}
          {images.length > 1 && (
            <div className="flex gap-1.5 overflow-x-auto pb-1 shrink-0">
              {images.map((url, i) => (
                <button
                  key={`${url}-${i}`}
                  onClick={() => setSelectedIdx(i)}
                  className={`relative shrink-0 rounded overflow-hidden w-12 h-12 border-2 transition-all ${
                    i === selectedIdx ? 'border-primary' : 'border-transparent hover:border-border'
                  }`}
                >
                  <img src={url} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}

          <div className="text-[10px] text-muted-foreground text-center shrink-0">
            {images.length} images · #{selectedIdx + 1} / {images.length}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-sm text-muted-foreground">
          <ImageOff className="w-10 h-10 mb-3 opacity-30" />
          <p>No media configured for this panel.</p>
          <p className="text-xs mt-1 max-w-[200px] text-center">
            Configure image URLs in the panel settings to display artifacts.
          </p>
        </div>
      )}
    </PanelWrapper>
  )
}
