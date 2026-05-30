{#
  Map a YouTube Data API v3 videoCategory id to a display name.
  Mirrors YOUTUBE_CATEGORY_NAMES in ingestion/google/youtube/enricher.py.
  Returns '' for an empty/unenriched id and 'Other' for an unknown id, so the
  dashboard never shows a bare numeric category.
#}
{% macro youtube_category_name(id_expr) %}
    if(
        ({{ id_expr }}) = '',
        '',
        transform(
            {{ id_expr }},
            ['1','2','10','15','17','18','19','20','21','22','23','24','25','26','27',
             '28','29','30','31','32','33','34','35','36','37','38','39','40','41','42','43','44'],
            ['Film & Animation','Autos & Vehicles','Music','Pets & Animals','Sports',
             'Short Movies','Travel & Events','Gaming','Videoblogging','People & Blogs',
             'Comedy','Entertainment','News & Politics','Howto & Style','Education',
             'Science & Technology','Nonprofits & Activism','Movies','Anime/Animation',
             'Action/Adventure','Classics','Comedy','Documentary','Drama','Family',
             'Foreign','Horror','Sci-Fi/Fantasy','Thriller','Shorts','Shows','Trailers'],
            'Other'
        )
    )
{% endmacro %}
