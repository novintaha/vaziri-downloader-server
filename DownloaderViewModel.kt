package com.vaziri.downloader

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vaziri.downloader.data.DownloadHelper
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class DownloaderViewModel : ViewModel() {

    private val _videoInfo = MutableStateFlow<VideoResponse?>(null)
    val videoInfo = _videoInfo.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage = _errorMessage.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading = _isLoading.asStateFlow()

    private val _downloadStatus = MutableStateFlow<String?>(null)
    val downloadStatus = _downloadStatus.asStateFlow()

    fun fetchVideoInfo(url: String) {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            try {
                val response = RetrofitClient.instance.getFormats(UrlRequest(url))
                _videoInfo.value = response
            } catch (e: Exception) {
                _errorMessage.value = "خطا: ${e.message}"
                e.printStackTrace()
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun downloadVideo(context: Context, url: String, formatId: String, title: String) {
        viewModelScope.launch {
            _downloadStatus.value = "در حال دانلود..."
            try {
                val response = RetrofitClient.instance.downloadVideo(DownloadRequest(url, formatId))
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body != null) {
                        val item = DownloadHelper.saveDownloadedFile(
                            context = context,
                            responseBody = body,
                            title = title,
                            url = url,
                            formatId = formatId
                        )
                        _downloadStatus.value = if (item != null) {
                            "✅ دانلود شد: ${item.title}"
                        } else {
                            "❌ خطا در ذخیره فایل"
                        }
                    } else {
                        _downloadStatus.value = "❌ فایلی دریافت نشد"
                    }
                } else {
                    _downloadStatus.value = "❌ خطای سرور: ${response.code()}"
                }
            } catch (e: Exception) {
                _downloadStatus.value = "❌ خطا: ${e.message}"
                e.printStackTrace()
            }
        }
    }

    fun clearDownloadStatus() {
        _downloadStatus.value = null
    }
}