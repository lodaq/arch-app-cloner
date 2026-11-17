# Maintainer: Arch Linux App Cloner Team
pkgname=arch-app-cloner
pkgver=1.0.0
pkgrel=1
pkgdesc="Run multiple isolated instances of any application with separate data, credentials, and custom badges"
arch=('any')
license=('MIT')
depends=('bubblewrap' 'dbus' 'python' 'python-pyside6')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
optdepends=(
    'xdg-utils: Open data directories and launch external URLs'
)
source=("$pkgname-$pkgver.tar.gz::local")

build() {
    python -m build --wheel --no-isolation
}

package() {
    python -m installer --destdir="$pkgdir" dist/*.whl

    # Install desktop entry and icon
    install -Dm644 arch-app-cloner.desktop "$pkgdir/usr/share/applications/arch-app-cloner.desktop"
    install -Dm644 assets/app-cloner.png "$pkgdir/usr/share/icons/hicolor/256x256/apps/app-cloner.png"
}
