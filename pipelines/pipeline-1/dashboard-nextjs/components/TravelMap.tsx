'use client';

import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

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
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    if (!isClient || !mapRef.current || mapInstanceRef.current) return;

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

    // Custom marker icon
    const customIcon = L.divIcon({
      className: 'custom-marker',
      html: `
        <div style="
          width: 12px;
          height: 12px;
          background: #A855F7;
          border: 2px solid #fff;
          border-radius: 50%;
          box-shadow: 0 0 10px rgba(168, 85, 247, 0.8);
        "></div>
      `,
      iconSize: [12, 12],
      iconAnchor: [6, 6],
    });

    // Add markers
    const markers: L.Marker[] = [];
    locations.forEach((location) => {
      const marker = L.marker([location.lat, location.lng], { icon: customIcon })
        .addTo(map)
        .bindPopup(`
          <div style="color: #1a1a1a; font-weight: 500;">
            ${location.name}
            <br/>
            <span style="font-size: 0.75rem; color: #666;">${location.duration}</span>
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
            color: '#A855F7',
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

    // Cleanup
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [locations, isClient]);

  if (!isClient) {
    return (
      <div className="w-full h-full bg-white/5 rounded-xl border border-white/10 flex items-center justify-center">
        <p className="text-white/50">Loading map...</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full rounded-xl overflow-hidden border border-white/10">
      <style jsx global>{`
        .leaflet-container {
          background: linear-gradient(to bottom right, #1a1a1a, #2d2d2d) !important;
        }
        .leaflet-tile-pane {
          opacity: 0.8;
        }
      `}</style>
      <div ref={mapRef} className="w-full h-full" />
    </div>
  );
}
