// screen_streamer.cpp
//
// This Windows-specific program uses GDI/GDI+ to capture the screen and Boost.Asio
// to serve a live MJPEG stream on the LAN. Compile with a C++ compiler linking against
// Gdiplus.lib, ws2_32.lib, and Boost libraries.

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <gdiplus.h>
#include <iostream>
#include <vector>
#include <mutex>
#include <thread>
#include <chrono>
#include <sstream>
#include <boost/asio.hpp>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "ws2_32.lib")

using namespace Gdiplus;
using boost::asio::ip::tcp;

// Global variables
std::mutex image_mutex;
std::vector<BYTE> latest_jpeg;
bool running = true;
ULONG jpeg_quality = 75; // JPEG quality (0-100)

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

// Helper function: Finds the CLSID of the JPEG encoder
int GetEncoderClsid(const WCHAR* format, CLSID* pClsid) {
    UINT num = 0, size = 0;
    GetImageEncodersSize(&num, &size);
    if (size == 0) return -1;

    auto pImageCodecInfo = (ImageCodecInfo*)(malloc(size));
    if (!pImageCodecInfo) return -1;

    GetImageEncoders(num, size, pImageCodecInfo);
    for (UINT j = 0; j < num; ++j) {
        if (wcscmp(pImageCodecInfo[j].MimeType, format) == 0) {
            *pClsid = pImageCodecInfo[j].Clsid;
            free(pImageCodecInfo);
            return j;
        }
    }

    free(pImageCodecInfo);
    return -1;
}

// Capture the entire screen and return JPEG-encoded data
std::vector<BYTE> CaptureScreenToJpeg() {
    std::vector<BYTE> buffer;

    int screenX = GetSystemMetrics(SM_XVIRTUALSCREEN);
    int screenY = GetSystemMetrics(SM_YVIRTUALSCREEN);
    int screenWidth = GetSystemMetrics(SM_CXVIRTUALSCREEN);
    int screenHeight = GetSystemMetrics(SM_CYVIRTUALSCREEN);

    HDC hScreenDC = GetDC(NULL);
    HDC hMemoryDC = CreateCompatibleDC(hScreenDC);
    HBITMAP hBitmap = CreateCompatibleBitmap(hScreenDC, screenWidth, screenHeight);

    if (!hBitmap) {
        DeleteDC(hMemoryDC);
        ReleaseDC(NULL, hScreenDC);
        return buffer;
    }

    SelectObject(hMemoryDC, hBitmap);

    if (!BitBlt(hMemoryDC, 0, 0, screenWidth, screenHeight, hScreenDC, screenX, screenY, SRCCOPY | CAPTUREBLT)) {
        DeleteObject(hBitmap);
        DeleteDC(hMemoryDC);
        ReleaseDC(NULL, hScreenDC);
        return buffer;
    }

    Bitmap bitmap(hBitmap, NULL);

    CLSID clsidEncoder;
    if (GetEncoderClsid(L"image/jpeg", &clsidEncoder) < 0) {
        DeleteObject(hBitmap);
        DeleteDC(hMemoryDC);
        ReleaseDC(NULL, hScreenDC);
        return buffer;
    }

    IStream* pStream = nullptr;
    if (CreateStreamOnHGlobal(NULL, TRUE, &pStream) != S_OK) {
        DeleteObject(hBitmap);
        DeleteDC(hMemoryDC);
        ReleaseDC(NULL, hScreenDC);
        return buffer;
    }

    EncoderParameters encoderParams;
    encoderParams.Count = 1;
    encoderParams.Parameter[0].Guid = EncoderQuality;
    encoderParams.Parameter[0].Type = EncoderParameterValueTypeLong;
    encoderParams.Parameter[0].NumberOfValues = 1;
    encoderParams.Parameter[0].Value = &jpeg_quality;

    if (bitmap.Save(pStream, &clsidEncoder, &encoderParams) != Ok) {
        pStream->Release();
        DeleteObject(hBitmap);
        DeleteDC(hMemoryDC);
        ReleaseDC(NULL, hScreenDC);
        return buffer;
    }

    STATSTG statstg;
    if (pStream->Stat(&statstg, STATFLAG_NONAME) != S_OK) {
        pStream->Release();
        DeleteObject(hBitmap);
        DeleteDC(hMemoryDC);
        ReleaseDC(NULL, hScreenDC);
        return buffer;
    }

    ULONG size = statstg.cbSize.LowPart;
    buffer.resize(size);
    LARGE_INTEGER liZero = {};
    pStream->Seek(liZero, STREAM_SEEK_SET, NULL);
    pStream->Read(buffer.data(), size, NULL);

    pStream->Release();
    DeleteObject(hBitmap);
    DeleteDC(hMemoryDC);
    ReleaseDC(NULL, hScreenDC);

    return buffer;
}

// Thread function to continuously capture the screen
void captureThreadFunc() {
    while (running) {
        auto jpegData = CaptureScreenToJpeg();
        if (!jpegData.empty()) {
            std::lock_guard<std::mutex> lock(image_mutex);
            latest_jpeg = std::move(jpegData);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

// Handle a single HTTP MJPEG client
void handleClient(tcp::socket socket) {
    try {
        std::string header =
            "HTTP/1.0 200 OK\r\n"
            "Server: CppScreenStreamer\r\n"
            "Cache-Control: no-cache\r\n"
            "Pragma: no-cache\r\n"
            "Content-Type: multipart/x-mixed-replace; boundary=--myboundary\r\n\r\n";
        boost::asio::write(socket, boost::asio::buffer(header));

        while (running) {
            std::vector<BYTE> frame;
            {
                std::lock_guard<std::mutex> lock(image_mutex);
                frame = latest_jpeg;
            }

            if (!frame.empty()) {
                std::ostringstream oss;
                oss << "--myboundary\r\n"
                    << "Content-Type: image/jpeg\r\n"
                    << "Content-Length: " << frame.size() << "\r\n\r\n";
                boost::asio::write(socket, boost::asio::buffer(oss.str()));
                boost::asio::write(socket, boost::asio::buffer(frame));
                boost::asio::write(socket, boost::asio::buffer("\r\n"));
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
    catch (std::exception& e) {
        std::cerr << "Client connection error: " << e.what() << std::endl;
    }
}

// Get local IP address
std::string getLocalIPAddress() {
    try {
        boost::asio::io_context io_context;
        tcp::resolver resolver(io_context);
        auto endpoints = resolver.resolve(boost::asio::ip::host_name(), "");
        for (const auto& entry : endpoints) {
            auto ep = entry.endpoint();
            if (ep.address().is_v4() && ep.address().to_string().substr(0, 4) != "127.") {
                return ep.address().to_string();
            }
        }
    }
    catch (...) {}
    return "127.0.0.1";
}

int main() {
    EnableDPIAwareness(); // New: prevent scaling issues on high-DPI screens

    GdiplusStartupInput gdiplusStartupInput;
    ULONG_PTR gdiplusToken;
    GdiplusStartup(&gdiplusToken, &gdiplusStartupInput, NULL);

    std::thread captureThread(captureThreadFunc);

    try {
        boost::asio::io_context io_context;
        tcp::acceptor acceptor(io_context, tcp::endpoint(tcp::v4(), 8080));
        std::string localIP = getLocalIPAddress();
        std::cout << "Screen stream available at http://" << localIP << ":8080/\n";

        while (running) {
            tcp::socket socket(io_context);
            acceptor.accept(socket);
            std::thread clientThread(handleClient, std::move(socket));
            clientThread.detach();
        }
    }
    catch (std::exception& e) {
        std::cerr << "Server error: " << e.what() << std::endl;
    }

    running = false;
    captureThread.join();
    GdiplusShutdown(gdiplusToken);
    return 0;
}
