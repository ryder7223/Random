#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <boost/asio.hpp>
#include <iostream>
#include <thread>
#include <vector>
#include <mutex>
#include <turbojpeg.h>

#pragma comment(lib, "ws2_32.lib")

std::mutex frame_mutex;
std::vector<unsigned char> latest_jpeg;
bool running = true;
int jpeg_quality = 75;

using boost::asio::ip::tcp;

// Set process DPI awareness (important for high-DPI screens)
void EnableDPIAwareness() {
    typedef BOOL(WINAPI* SetProcessDPIAwareFunc)(void);
    HMODULE user32 = LoadLibraryA("user32.dll");
    if (user32) {
        SetProcessDPIAwareFunc setDPIAware = (SetProcessDPIAwareFunc)GetProcAddress(user32, "SetProcessDPIAware");
        if (setDPIAware) setDPIAware();
        FreeLibrary(user32);
    }
}

std::vector<unsigned char> captureScreenAsJPEG() {
    std::vector<unsigned char> jpegData;

    // Capture the virtual screen dimensions
    int x = GetSystemMetrics(SM_XVIRTUALSCREEN);
    int y = GetSystemMetrics(SM_YVIRTUALSCREEN);
    int width = GetSystemMetrics(SM_CXVIRTUALSCREEN);
    int height = GetSystemMetrics(SM_CYVIRTUALSCREEN);

    HDC hScreenDC = GetDC(NULL);  // Get the entire screen device context
    HDC hMemoryDC = CreateCompatibleDC(hScreenDC);
    HBITMAP hBitmap = CreateCompatibleBitmap(hScreenDC, width, height);
    SelectObject(hMemoryDC, hBitmap);

    // Perform the capture using BitBlt with the appropriate offsets and dimensions
    BitBlt(hMemoryDC, 0, 0, width, height, hScreenDC, x, y, SRCCOPY | CAPTUREBLT);

    BITMAPINFO bi = {};
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = width;
    bi.bmiHeader.biHeight = -height; // Top-down DIB
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 24;
    bi.bmiHeader.biCompression = BI_RGB;

    // GetDIBits uses 4-byte aligned stride, so we use it first
    int win_stride = ((width * 3 + 3) & ~3);
    std::vector<unsigned char> dibData(win_stride * height);
    GetDIBits(hMemoryDC, hBitmap, 0, height, dibData.data(), &bi, DIB_RGB_COLORS);

    // TurboJPEG needs tight-packed data (no padding), so we convert it
    int tj_stride = width * 3;
    std::vector<unsigned char> packedData(tj_stride * height);

    for (int i = 0; i < height; ++i) {
        memcpy(&packedData[i * tj_stride], &dibData[i * win_stride], tj_stride);
    }

    // Encode using TurboJPEG
    tjhandle compressor = tjInitCompress();
    unsigned char* jpegBuf = nullptr;
    unsigned long jpegSize = 0;

    tjCompress2(compressor,
        packedData.data(),
        width,
        tj_stride, // CORRECT: tight-packed stride
        height,
        TJPF_BGR,
        &jpegBuf,
        &jpegSize,
        TJSAMP_420,
        jpeg_quality,
        TJFLAG_FASTDCT);

    jpegData.assign(jpegBuf, jpegBuf + jpegSize);
    tjFree(jpegBuf);
    tjDestroy(compressor);

    DeleteObject(hBitmap);
    DeleteDC(hMemoryDC);
    ReleaseDC(NULL, hScreenDC);

    return jpegData;
}

void captureLoop() {
    while (running) {
        auto data = captureScreenAsJPEG();
        if (!data.empty()) {
            std::lock_guard<std::mutex> lock(frame_mutex);
            latest_jpeg = std::move(data);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(30)); // ~30 FPS
    }
}

void clientHandler(tcp::socket socket) {
    try {
        std::string boundary = "myboundary";

        std::ostringstream header;
        header << "HTTP/1.0 200 OK\r\n"
               << "Server: TurboJPEGStreamer\r\n"
               << "Cache-Control: no-cache\r\n"
               << "Pragma: no-cache\r\n"
               << "Content-Type: multipart/x-mixed-replace; boundary=" << boundary << "\r\n"
               << "\r\n";

        boost::asio::write(socket, boost::asio::buffer(header.str()));

        while (running) {
            std::vector<unsigned char> frame;
            {
                std::lock_guard<std::mutex> lock(frame_mutex);
                frame = latest_jpeg;
            }

            if (!frame.empty()) {
                std::ostringstream oss;
                oss << "--" << boundary << "\r\n"
                    << "Content-Type: image/jpeg\r\n"
                    << "Content-Length: " << frame.size() << "\r\n"
                    << "\r\n"; // Important!

                boost::asio::write(socket, boost::asio::buffer(oss.str()));
                boost::asio::write(socket, boost::asio::buffer(frame));
                boost::asio::write(socket, boost::asio::buffer("\r\n")); // Each part ends with a CRLF
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(33)); // ~30 FPS
        }
    }
    catch (...) {
        // Client disconnected or error occurred
    }
}


std::string getLocalIP() {
    try {
        boost::asio::io_context ctx;
        tcp::resolver resolver(ctx);
        auto endpoints = resolver.resolve(boost::asio::ip::host_name(), "");
        for (auto& e : endpoints) {
            auto addr = e.endpoint().address();
            if (addr.is_v4() && addr.to_string().substr(0, 4) != "127.")
                return addr.to_string();
        }
    }
    catch (...) {}
    return "127.0.0.1";
}

int main() {
    EnableDPIAwareness(); // Prevent DPI scaling issues

    std::cout << "Starting screen capture server...\n";
    std::thread captureThread(captureLoop);

    try {
        boost::asio::io_context io_context;
        tcp::acceptor acceptor(io_context, tcp::endpoint(tcp::v4(), 8080));
        std::string ip = getLocalIP();
        std::cout << "Stream available at: http://" << ip << ":8080/\n";

        while (running) {
            tcp::socket socket(io_context);
            acceptor.accept(socket);
            std::thread(clientHandler, std::move(socket)).detach();
        }
    }
    catch (std::exception& e) {
        std::cerr << "Server error: " << e.what() << "\n";
    }

    running = false;
    captureThread.join();
    return 0;
}
