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

const escapeHtml = (s: string) =>
  s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string));

export function TravelMap({ locations }: TravelMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    let isMounted = true;

    const initMap = async () => {
      try {
        // Leaflet + the marker-cluster plugin (extends L) — client-only.
        const L = (await import('leaflet')).default;
        await import('leaflet.markercluster');
        await import('leaflet/dist/leaflet.css');
        await import('leaflet.markercluster/dist/MarkerCluster.css');

        if (!isMounted || !mapRef.current || mapInstanceRef.current) return;

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

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 19,
          noWrap: true,
        }).addTo(map);

        // Leaf marker: flat dot at rest; glow on hover (DESIGN.md §4 Flat-Rest).
        const customIcon = L.divIcon({
          className: 'travel-marker',
          html: `<div class="travel-marker-dot"></div>`,
          iconSize: [12, 12],
          iconAnchor: [6, 6],
        });

        // Cluster the ~hundreds of neighbourhood points so dense metros collapse
        // into a single count bubble that expands on zoom — instead of an
        // unreadable pile of overlapping dots. (No connector lines: the points
        // are ranked by activity, not a travel route, so lines would be noise.)
        const clusterGroup = (L as typeof L & {
          markerClusterGroup: (opts: Record<string, unknown>) => L.LayerGroup & {
            addLayer: (l: L.Layer) => void;
            getBounds: () => L.LatLngBounds;
          };
        }).markerClusterGroup({
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true,
          maxClusterRadius: 48,
          chunkedLoading: true,
          iconCreateFunction: (cluster: { getChildCount: () => number }) => {
            const n = cluster.getChildCount();
            const size = n < 10 ? 34 : n < 50 ? 42 : n < 150 ? 52 : 62;
            const tier = n < 10 ? 'sm' : n < 150 ? 'md' : 'lg';
            return L.divIcon({
              html: `<div class="travel-cluster travel-cluster-${tier}"><span>${n}</span></div>`,
              className: 'travel-cluster-wrap',
              iconSize: [size, size],
              iconAnchor: [size / 2, size / 2],
            });
          },
        });

        let added = 0;
        locations.forEach((location) => {
          if (!location.lat || !location.lng) return;
          const marker = L.marker([location.lat, location.lng], { icon: customIcon }).bindPopup(
            `<div class="travel-popup"><div class="travel-popup-name">${escapeHtml(location.name)}</div></div>`,
          );
          clusterGroup.addLayer(marker);
          added += 1;
        });
        map.addLayer(clusterGroup);

        if (added > 0) {
          map.fitBounds(clusterGroup.getBounds().pad(0.1));
        }

        setIsLoading(false);
      } catch (error) {
        console.error('Error initializing map:', error);
        setIsLoading(false);
      }
    };

    initMap();

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

        /* Leaf marker — flat at rest, glow on hover (Flat-Rest Rule) */
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

        /* Cluster bubble — violet, count-labelled, sized by tier */
        .travel-cluster-wrap { background: transparent; }
        .travel-cluster {
          display: flex; align-items: center; justify-content: center;
          width: 100%; height: 100%;
          background: ${CHANNEL_HEX.maps}26;
          border: 1.5px solid ${CHANNEL_HEX.maps};
          border-radius: 9999px;
          color: #FFFFFF;
          font-family: "IBM Plex Mono", ui-monospace, monospace;
          font-weight: 600;
          box-shadow: 0 0 0 4px ${CHANNEL_HEX.maps}14;
          transition: box-shadow 200ms cubic-bezier(0.22, 1, 0.36, 1);
        }
        .travel-cluster span { font-size: 0.7rem; line-height: 1; }
        .travel-cluster-lg span { font-size: 0.85rem; }
        .travel-cluster-wrap:hover .travel-cluster { box-shadow: 0 0 14px ${CHANNEL_HEX.maps}aa; }

        /* Popup — Rack Black surface */
        .leaflet-popup-content-wrapper {
          background: #1A1A1A;
          color: #FFFFFF;
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 8px;
        }
        .leaflet-popup-tip { background: #1A1A1A; border: 1px solid rgba(255,255,255,0.1); }
        .travel-popup-name { font-weight: 500; }
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
