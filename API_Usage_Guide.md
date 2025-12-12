# Product API Usage Guide - Frontend Integration

## 🏪 Two Product Systems Available

### 1️⃣ **BILLING SYSTEM PRODUCTS** (Custom Jewelry)
```
Base URL: /products/
```

#### **List Products**
```bash
GET /products/?page=1&page_size=20
```
**Response:**
```json
{
  "total": 50,
  "products": [
    {
      "id": "uuid",
      "title": "Classic Solitaire Ring",
      "variants": [
        {
          "sku": "CR-001-18K",
          "price": 79999.00,
          "metal_components": [...],
          "diamond_components": [...]
        }
      ]
    }
  ]
}
```

#### **Get Single Product**
```bash
GET /products/{product_id}
```

---

### 2️⃣ **ZAKYA PRODUCTS** (Inventory Jewelry)
```
Base URL: /products/zakya/
```

#### **List Zakya Products** (Most Used)
```bash
GET /products/zakya/products?page=1&page_size=20&with_images=true
```

#### **Advanced Filtering**
```bash
GET /products/zakya/products?search_query=gold ring&category_list=Rings,Earrings&price_min=10000&price_max=50000&brand_list=Minaki&stock_min=1&with_images=true
```

**Response:**
```json
{
  "success": true,
  "total": 150,
  "products": [
    {
      "item_id": "ZAK001",
      "name": "Gold Ring",
      "sku": "GR001",
      "rate": 45000.0,
      "brand": "Minaki",
      "category_name": "Rings",
      "stock_on_hand": 5.0,
      "shopify_image": {
        "url": "https://cdn.shopify.com/image.jpg",
        "alt_text": "Gold Ring"
      }
    }
  ],
  "page": 1,
  "total_pages": 8
}
```

#### **Get Single Zakya Product**
```bash
GET /products/zakya/products/{sku}?with_image=true
```

#### **Update Single Zakya Product**
```bash
PATCH /products/zakya/products/{sku}?name=Updated Ring&rate=55000&stock_on_hand=10
```

#### **Bulk Update Zakya Products**
```bash
PATCH /products/zakya/products/bulk-update
```
**Body:**
```json
{
  "filter_criteria": {
    "brand": "Minaki",
    "category_name": "Rings"
  },
  "updates": {
    "rate": 50000,
    "brand": "Updated Brand"
  }
}
```

---

## 🎯 **Frontend Usage Examples**

### **Product Listing Page**
```javascript
// For Zakya inventory products
const response = await fetch('/products/zakya/products?page=1&page_size=20&with_images=true');
const data = await response.json();
// data.products = array of products with images
```

### **Search & Filter**
```javascript
// Search with filters
const params = new URLSearchParams({
  search_query: 'gold ring',
  category_list: 'Rings,Earrings',
  price_min: 10000,
  price_max: 50000,
  with_images: true
});
const response = await fetch(`/products/zakya/products?${params}`);
```

### **Product Details Page**
```javascript
// Get single product by SKU
const response = await fetch(`/products/zakya/products/${sku}?with_image=true`);
const data = await response.json();
// data.product = single product with image
```

### **Update Product**
```javascript
// Update single product
const response = await fetch(`/products/zakya/products/${sku}?rate=55000&stock_on_hand=10`, {
  method: 'PATCH'
});

// Bulk update products
const response = await fetch('/products/zakya/products/bulk-update', {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    filter_criteria: { brand: 'Minaki' },
    updates: { rate: 50000 }
  })
});
```

---

## 📋 **Available Filters**

| Filter | Type | Example |
|--------|------|---------|
| `search_query` | Text | `"gold ring"` |
| `category_list` | CSV | `"Rings,Earrings"` |
| `brand_list` | CSV | `"Minaki,Premium"` |
| `price_min/max` | Number | `10000` |
| `stock_min` | Number | `1` |
| `with_images` | Boolean | `true` |

---

## 🚀 **Quick Start**

1. **List all products:** `GET /products/zakya/products`
2. **Search products:** `GET /products/zakya/products?search_query=gold`
3. **Filter by category:** `GET /products/zakya/products?category_list=Rings`
4. **Get product details:** `GET /products/zakya/products/{sku}`