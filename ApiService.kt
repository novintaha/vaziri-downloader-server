package com.vaziri.downloader

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Streaming

interface ApiService {
    @POST("formats")
    suspend fun getFormats(@Body request: UrlRequest): VideoResponse

    @Streaming
    @POST("download")
    suspend fun downloadVideo(@Body request: DownloadRequest): Response<ResponseBody>
}