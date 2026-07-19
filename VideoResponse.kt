package com.vaziri.downloader

data class Format(
    val format_id: String,
    val ext: String,
    val resolution: String,
    val filesize: Long? = null,
    val vcodec: String? = "none",
    val acodec: String? = "none",
    val stream_url: String? = null
)

data class VideoResponse(
    val title: String,
    val thumbnail: String? = null,
    val duration: Int? = null,
    val formats: List<Format> = emptyList()
)

data class UrlRequest(
    val url: String,
    val use_subtitles: Boolean = false
)

data class DownloadRequest(
    val url: String,
    val format_id: String,
    val use_subtitles: Boolean = false
)