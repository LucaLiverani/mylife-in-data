interface RecentEventItemProps {
  event: {
    type: string;
    title: string;
    subtitle: string;
    time: string;
    image?: string;
    color: string;
  };
}

export function RecentEventItem({ event }: RecentEventItemProps) {
  return (
    <div
      className="group relative"
      style={{
        borderLeft: `3px solid ${event.color}`,
      }}
    >
      <div
        className="flex items-center gap-3 py-2 px-3 rounded-r-lg transition-all duration-300 hover:shadow-lg"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.02)',
          boxShadow: `0 0 0 ${event.color}00`,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = `${event.color}10`;
          e.currentTarget.style.boxShadow = `0 4px 20px ${event.color}40`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)';
          e.currentTarget.style.boxShadow = `0 0 0 ${event.color}00`;
        }}
      >
        {event.image ? (
          <img
            src={event.image}
            alt={event.title}
            className="w-10 h-10 rounded-md object-cover flex-shrink-0"
          />
        ) : (
          <div
            className="w-10 h-10 rounded-md flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: `${event.color}20` }}
          >
            {event.type === 'spotify' && (
              <svg className="w-5 h-5" fill={event.color} viewBox="0 0 24 24">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
              </svg>
            )}
            {event.type === 'youtube' && (
              <svg className="w-5 h-5" fill={event.color} viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            )}
            {event.type === 'google' && (
              <svg className="w-5 h-5" fill={event.color} viewBox="0 0 24 24">
                <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
              </svg>
            )}
            {event.type === 'maps' && (
              <svg className="w-5 h-5" fill={event.color} viewBox="0 0 24 24">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
              </svg>
            )}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm truncate">{event.title}</p>
          <p className="text-xs text-white/60 truncate">{event.subtitle}</p>
        </div>
        <p className="text-xs text-white/40 flex-shrink-0">{event.time}</p>
      </div>
    </div>
  );
}
