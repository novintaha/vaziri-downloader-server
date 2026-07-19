package com.vaziri.downloader

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.annotation.OptIn
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.ProgressiveMediaSource
import androidx.media3.ui.PlayerView
import com.vaziri.downloader.data.DownloadItem
import java.net.URLEncoder

val BrandPurple = Color(0xFF6200EA)
val BrandPurpleDark = Color(0xFF311B92)
val AccentGreen = Color(0xFF00C853)
val CardBg = Color(0xFFFFFFFF)
val BgColor = Color(0xFFF5F5F7)
val TextDark = Color(0xFF212121)
val TextGray = Color(0xFF757575)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = BgColor) {
                    DownloaderScreen()
                }
            }
        }
    }
}

@Composable
fun DownloaderScreen(viewModel: DownloaderViewModel = viewModel()) {
    var url by remember { mutableStateOf("") }
    var useSubtitles by remember { mutableStateOf(false) }
    var playingVideoUrl by remember { mutableStateOf<String?>(null) }

    val videoInfo by viewModel.videoInfo.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val errorMessage by viewModel.errorMessage.collectAsState()
    val downloadHistory by viewModel.downloadHistory.collectAsState()
    val downloadProgress by viewModel.downloadProgress.collectAsState()
    val keyboardController = LocalSoftwareKeyboardController.current

    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize()) {
            HeaderSection()

            Column(modifier = Modifier.fillMaxWidth().weight(1f).padding(horizontal = 20.dp)) {
                Spacer(modifier = Modifier.height((-45).dp))

                Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(26.dp), color = CardBg, shadowElevation = 12.dp) {
                    Column(modifier = Modifier.padding(18.dp)) {
                        OutlinedTextField(
                            value = url,
                            onValueChange = { url = it },
                            placeholder = { Text("لینک ویدیو را وارد کنید", fontSize = 13.sp) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(18.dp),
                            singleLine = true,
                            enabled = !isLoading,
                            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = BrandPurple)
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().clickable { useSubtitles = !useSubtitles }) {
                            Checkbox(checked = useSubtitles, onCheckedChange = { useSubtitles = it }, colors = CheckboxDefaults.colors(checkedColor = BrandPurple))
                            Text("🌐", fontSize = 18.sp)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("ترجمه و چسباندن زیرنویس فارسی", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = if(useSubtitles) BrandPurple else TextGray)
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        Button(
                            onClick = { if (url.isNotBlank()) { keyboardController?.hide(); viewModel.fetchVideoInfo(url, useSubtitles) } },
                            modifier = Modifier.fillMaxWidth().height(52.dp),
                            shape = RoundedCornerShape(16.dp),
                            enabled = !isLoading,
                            colors = ButtonDefaults.buttonColors(containerColor = BrandPurple)
                        ) {
                            Text("🔍 بررسی تمام فرمت‌ها", fontWeight = FontWeight.Bold)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                errorMessage?.let { msg ->
                    val isSuccess = msg.contains("✅") || msg.contains("⏳")
                    Card(
                        colors = CardDefaults.cardColors(containerColor = if (isSuccess) AccentGreen.copy(alpha = 0.1f) else Color.Red.copy(alpha = 0.1f)),
                        modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp),
                        shape = RoundedCornerShape(14.dp)
                    ) {
                        Column(modifier = Modifier.padding(12.dp).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(text = msg, color = if (isSuccess) AccentGreen else Color.Red, textAlign = TextAlign.Center, fontWeight = FontWeight.Bold, fontSize = 13.sp)

                            downloadProgress?.let { progress ->
                                Spacer(modifier = Modifier.height(8.dp))
                                LinearProgressIndicator(
                                    progress = { progress / 100f },
                                    modifier = Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(4.dp)),
                                    color = AccentGreen
                                )
                                Text("$progress%", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }

                Box(modifier = Modifier.weight(1f)) {
                    if (videoInfo != null) {
                        TabbedFormatsSection(videoInfo!!, viewModel, url, useSubtitles) { directLink ->
                            playingVideoUrl = directLink
                        }
                    } else {
                        HistorySection(downloadHistory)
                    }
                }
            }
        }

        if (isLoading && downloadProgress == null) {
            Box(modifier = Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.4f)), contentAlignment = Alignment.Center) {
                Card(shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                    Column(modifier = Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = BrandPurple)
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("در حال پردازش...", fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        if (playingVideoUrl != null) {
            VideoPlayerDialog(url = playingVideoUrl!!, onDismiss = { playingVideoUrl = null })
        }
    }
}

@Composable
fun TabbedFormatsSection(info: VideoResponse, viewModel: DownloaderViewModel, originalUrl: String, useSubtitles: Boolean, onPlay: (String) -> Unit) {
    var selectedTab by remember { mutableStateOf(0) }
    val tabs = listOf("🎬 ویدیو", "🎵 صدا")

    val videoFormats = info.formats.filter {
        it.ext != "mhtml" && !it.format_id.contains("storyboard") && (it.vcodec != "none" && it.vcodec != null)
    }.sortedByDescending { it.resolution.substringAfter("x", "0").toIntOrNull() ?: 0 }

    val audioFormats = info.formats.filter {
        it.ext != "mhtml" && !it.format_id.contains("storyboard") && (it.acodec != "none" && it.acodec != null)
    }.sortedByDescending { it.filesize ?: 0L }

    Column {
        Text(info.title, fontWeight = FontWeight.ExtraBold, maxLines = 1, color = TextDark, fontSize = 16.sp)
        Spacer(modifier = Modifier.height(8.dp))

        TabRow(selectedTabIndex = selectedTab, containerColor = Color.Transparent, contentColor = BrandPurple, divider = {}) {
            tabs.forEachIndexed { index, title ->
                Tab(selected = selectedTab == index, onClick = { selectedTab = index }, text = { Text(title, fontWeight = FontWeight.Bold) })
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        val currentFormats = if (selectedTab == 0) videoFormats else audioFormats

        if (currentFormats.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("فرمت خاصی در این بخش پیدا نشد", color = TextGray)
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 20.dp)) {
                items(currentFormats) { format ->
                    FormatCard(format, info.title, originalUrl, useSubtitles, onPlay) {
                        viewModel.startDownload(originalUrl, info.title, format.format_id, useSubtitles)
                    }
                }
            }
        }
    }
}

@Composable
fun FormatCard(format: Format, title: String, originalUrl: String, useSubtitles: Boolean, onPlay: (String) -> Unit, onClick: () -> Unit) {
    val context = LocalContext.current
    val isAudio = format.vcodec == "none" || format.vcodec == null
    val displayRes = if (isAudio) "صوتی (${format.ext.uppercase()})" else "کیفیت " + format.resolution.substringAfter("x", format.resolution)

    val encodedUrl = URLEncoder.encode(originalUrl, "UTF-8")
    val directLink = "https://vaziri-downloader-server.onrender.com/download_direct?url=$encodedUrl&format_id=${format.format_id}${if(useSubtitles) "&use_subtitles=true" else ""}"

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(modifier = Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(modifier = Modifier.size(45.dp).clip(RoundedCornerShape(12.dp)).background(if(isAudio) AccentGreen.copy(alpha = 0.1f) else BrandPurple.copy(alpha = 0.1f)), contentAlignment = Alignment.Center) {
                Text(if (isAudio) "🎵" else "🎬", fontSize = 22.sp)
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(displayRes, fontWeight = FontWeight.Bold, color = TextDark, fontSize = 14.sp)
                Text("حجم: ${if(format.filesize != null) "${format.filesize/1024/1024} MB" else "محاسبه در سرور"}", fontSize = 12.sp, color = TextGray)
            }

            IconButton(onClick = { format.stream_url?.let { onPlay(it) } }) {
                Icon(Icons.Default.PlayArrow, contentDescription = "Play", tint = AccentGreen)
            }

            IconButton(onClick = {
                val shareText = "دانلود و تماشای آنلاین: $title\n\nلینک مستقیم برای شما (کپی کرده و در مرورگر بزنید):\n$directLink"
                val sendIntent = Intent(Intent.ACTION_SEND).apply {
                    putExtra(Intent.EXTRA_TEXT, shareText)
                    type = "text/plain"
                }
                context.startActivity(Intent.createChooser(sendIntent, "ارسال لینک به:"))
            }) {
                Icon(Icons.Default.Share, contentDescription = "Share", tint = BrandPurple)
            }

            IconButton(onClick = onClick) {
                Text("⬇️", fontSize = 20.sp)
            }
        }
    }
}

@OptIn(UnstableApi::class)
@Composable
fun VideoPlayerDialog(url: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var isBuffering by remember { mutableStateOf(true) }

    val exoPlayer = remember {
        val dataSourceFactory = DefaultHttpDataSource.Factory()
            .setUserAgent("Mozilla/5.0")
            .setAllowCrossProtocolRedirects(true)

        ExoPlayer.Builder(context).build().apply {
            setMediaSource(ProgressiveMediaSource.Factory(dataSourceFactory).createMediaSource(MediaItem.fromUri(url)))
            prepare()
            playWhenReady = true
            addListener(object : Player.Listener {
                override fun onPlaybackStateChanged(state: Int) {
                    isBuffering = state == Player.STATE_BUFFERING || state == Player.STATE_IDLE
                }
            })
        }
    }

    DisposableEffect(Unit) { onDispose { exoPlayer.release() } }

    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(modifier = Modifier.fillMaxSize(), color = Color.Black) {
            Box(modifier = Modifier.fillMaxSize()) {
                AndroidView(factory = { ctx -> PlayerView(ctx).apply { player = exoPlayer } }, modifier = Modifier.fillMaxSize())

                if (isBuffering) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = Color.White)
                            Spacer(modifier = Modifier.height(12.dp))
                            Text("در حال آماده‌سازی پخش...", color = Color.White, fontSize = 13.sp)
                        }
                    }
                }

                IconButton(onClick = onDismiss, modifier = Modifier.align(Alignment.TopEnd).padding(16.dp).background(Color.Black.copy(alpha = 0.5f), CircleShape) ) {
                    Icon(Icons.Default.Close, contentDescription = "Close", tint = Color.White)
                }
            }
        }
    }
}

@Composable
fun HeaderSection() {
    Box(modifier = Modifier.fillMaxWidth().height(260.dp).background(Brush.verticalGradient(listOf(BrandPurple, BrandPurpleDark))), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(modifier = Modifier.size(110.dp).shadow(20.dp, CircleShape), shape = CircleShape, color = Color.White) {
                Box(contentAlignment = Alignment.Center) { Text("📥", fontSize = 60.sp) }
            }
            Spacer(modifier = Modifier.height(16.dp))
            Text("Vaziri Downloader", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Black)
            Text("دانلودر هوشمند یوتیوب و اینستاگرام", color = Color.White.copy(alpha = 0.8f), fontSize = 15.sp)
        }
    }
}

@Composable
fun HistorySection(history: List<DownloadItem>) {
    Column {
        Text("تاریخچه دانلود", fontWeight = FontWeight.Bold, fontSize = 18.sp, color = TextDark)
        Spacer(modifier = Modifier.height(10.dp))
        if (history.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize().padding(top = 40.dp), contentAlignment = Alignment.TopCenter) {
                Text("هنوز چیزی دانلود نکردی! 😊", color = TextGray)
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(history) { item ->
                    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text("✅", modifier = Modifier.padding(end = 8.dp))
                            Text(item.title, maxLines = 1, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f), fontSize = 13.sp)
                        }
                    }
                }
            }
        }
    }
}