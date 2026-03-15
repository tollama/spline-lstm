package ai.tollama.splineforecast.mobile

import java.io.File
import java.io.InputStream
import java.security.MessageDigest

object ModelChecksumVerifier {
    fun sha256(file: File): String = file.inputStream().use { sha256(it) }

    fun sha256(stream: InputStream): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            val read = stream.read(buffer)
            if (read <= 0) break
            digest.update(buffer, 0, read)
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    fun verify(file: File, expectedSha256: String): Boolean {
        return sha256(file).equals(expectedSha256, ignoreCase = true)
    }
}
