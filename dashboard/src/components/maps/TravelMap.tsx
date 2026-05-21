import { useEffect, useRef, useState } from 'react';
import type L from 'leaflet';
import { CHANNEL_HEX } from '@/lib/channels';

interface TravelMapProps {
  locations: Array<{
    name: string;
    lat: number;
    lng: number;
    duration: string;
  }>;
}

export function TravelMap({ locations }: TravelMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    let isMounted = true;

    const initMap = async () => {
      try {
        // Dynamically import Leaflet only on client side
        const L = (await import('leaflet')).default;
        // @ts-expect-error — CSS side-effect import; Vite handles, tsc cannot resolve.
        await import('leaflet/dist/leaflet.css');

        if (!isMounted || !mapRef.current || mapInstanceRef.current) return;

        // Initialize map
        const map = L.map(mapRef.current, {
          center: [20, 0],
          zoom: 2,
          zoomControl: true,
          scrollWheelZoom: true,
          minZoom: 2,
          maxBounds: [[-90, -180], [90, 180]],
          maxBoundsViscosity: 1.0,
        });

        mapInstanceRef.current = map;

        // Dark tile layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 19,
          noWrap: true,
        }).addTo(map);

        // Custom marker: flat at rest; glow lives in the hover handler below.
        // (DESIGN.md §4 Flat-Rest Rule — shadow is a response, not decoration.)
        const customIcon = L.divIcon({
          className: 'travel-marker',
          html: `<div class="travel-marker-dot"></div>`,
          iconSize: [12, 12],
          iconAnchor: [6, 6],
        });

        // Add markers
        const markers: L.Marker[] = [];
        locations.forEach((location) => {
          const marker = L.marker([location.lat, location.lng], { icon: customIcon })
            .addTo(map)
            .bindPopup(`
              <div class="travel-popup">
                <div class="travel-popup-name">${location.name}</div>
                <div class="travel-popup-meta">${location.duration}</div>
              </div>
            `);
          markers.push(marker);
        });

        // Draw connections between consecutive locations
        if (locations.length > 1) {
          for (let i = 0; i < locations.length - 1; i++) {
            const from = locations[i];
            const to = locations[i + 1];

            L.polyline(
              [[from.lat, from.lng], [to.lat, to.lng]],
              {
                color: CHANNEL_HEX.maps,
                weight: 2,
                opacity: 0.6,
                dashArray: '5, 10',
              }
            ).addTo(map);
          }
        }

        // Fit bounds to show all markers
        if (markers.length > 0) {
          const group = L.featureGroup(markers);
          map.fitBounds(group.getBounds().pad(0.1));
        }

        setIsLoading(false);
      } catch (error) {
        console.error('Error initializing map:', error);
        setIsLoading(false);
      }
    };

    initMap();

    // Cleanup
    return () => {
      isMounted = false;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [locations]);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-md border border-signal-white/10">
      <style>{`
        .leaflet-container {
          background: linear-gradient(to bottom right, var(--rack-black, #1A1A1A), var(--rack-charcoal, #2D2D2D)) !important;
        }
        .leaflet-tile-pane { opacity: 0.8; }

        /* Marker — flat at rest, glow on hover (Flat-Rest Rule) */
        .travel-marker-dot {
          width: 12px;
          height: 12px;
          background: ${CHANNEL_HEX.maps};
          border: 2px solid rgba(255,255,255,0.92);
          border-radius: 50%;
          transition: box-shadow 200ms cubic-bezier(0.22, 1, 0.36, 1);
        }
        .travel-marker:hover .travel-marker-dot,
        .travel-marker:focus-visible .travel-marker-dot {
          box-shadow: 0 0 12px ${CHANNEL_HEX.maps}cc;
        }

        /* Popup — Rack Black surface, mono meta */
        .leaflet-popup-content-wrapper {
          background: #1A1A1A;
          color: #FFFFFF;
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 8px;
        }
        .leaflet-popup-tip { background: #1A1A1A; border: 1px solid rgba(255,255,255,0.1); }
        .travel-popup-name { font-weight: 500; }
        .travel-popup-meta {
          margin-top: 4px;
          font-family: "IBM Plex Mono", ui-monospace, monospace;
          font-size: 0.75rem;
          color: rgba(255,255,255,0.6);
        }
      `}</style>
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-rack-black/80">
          <p className="font-mono text-sm uppercase tracking-wider text-signal-white/60">Plotting the route…</p>
        </div>
      )}
      <div ref={mapRef} className="h-full w-full" />
    </div>
  );
}
