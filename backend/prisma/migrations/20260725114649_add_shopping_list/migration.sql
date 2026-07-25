-- CreateEnum
CREATE TYPE "ShoppingListItemStatus" AS ENUM ('OPEN', 'ORDERED', 'DONE');

-- CreateTable
CREATE TABLE "shopping_list_items" (
    "id" TEXT NOT NULL,
    "itemId" TEXT,
    "customName" TEXT,
    "quantity" DECIMAL(12,3) NOT NULL,
    "note" TEXT,
    "status" "ShoppingListItemStatus" NOT NULL DEFAULT 'OPEN',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "resolvedAt" TIMESTAMP(3),

    CONSTRAINT "shopping_list_items_pkey" PRIMARY KEY ("id")
);

-- AddForeignKey
ALTER TABLE "shopping_list_items" ADD CONSTRAINT "shopping_list_items_itemId_fkey" FOREIGN KEY ("itemId") REFERENCES "items"("id") ON DELETE SET NULL ON UPDATE CASCADE;
