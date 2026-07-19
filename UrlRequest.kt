package com.vaziri.downloader

data class UrlRequest(
    val url: String
)

data class DownloadRequest(
    val url: String,
    val format_id: String
)